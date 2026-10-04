import asyncio
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import flet as ft

from services.module_development_service import ModuleDevelopmentService
from services.module_registry_state import InvalidModuleInfo, ModuleRegistryState
from tests.module_test_utils import build_manifest, create_module_folder
from ui.home.view import HomeViewState
from ui.settings.module_developer_tab import ModuleDeveloperTab
from ui.settings.view import SETTINGS_TABS


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _ToasterSpy:
    def __init__(self) -> None:
        self.notifications: list[tuple[str, str, str]] = []

    def show_success(self, message: str, title: str = "Sucesso") -> None:
        self.notifications.append(("success", title, message))

    def show_warning(self, message: str, title: str = "Atenção") -> None:
        self.notifications.append(("warning", title, message))

    def show_error(self, message: str, title: str = "Erro") -> None:
        self.notifications.append(("error", title, message))


class _RegistryStub:
    def __init__(self, state: ModuleRegistryState) -> None:
        self.state = state
        self.sync_count = 0

    def sync(self) -> ModuleRegistryState:
        self.sync_count += 1
        return self.state


class ModuleDeveloperModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.installed = self.root / "installed"
        self.service = ModuleDevelopmentService(
            installed_modules_dir=self.installed,
            examples_dir=PROJECT_ROOT / "modules" / "examples",
        )
        self.toaster = _ToasterSpy()

    def build_tab(
        self,
        *,
        registry_state: ModuleRegistryState | None = None,
    ) -> tuple[ModuleDeveloperTab, _RegistryStub]:
        registry = _RegistryStub(registry_state or ModuleRegistryState())
        tab = ModuleDeveloperTab(
            self.toaster,
            development_service=self.service,
            registry_factory=lambda: registry,
        )
        return tab, registry

    def test_settings_exposes_local_modules_tab(self) -> None:
        self.assertIn(
            ("modules", "Desenvolvimento"),
            [(key, label) for key, label, _ in SETTINGS_TABS],
        )

    def test_build_does_not_scan_folders_before_mount(self) -> None:
        tab, _ = self.build_tab()
        with patch.object(self.service, "list_installed_modules") as scan:
            tab.build()
        scan.assert_not_called()

    def test_repository_button_awaits_browser_launch(self) -> None:
        tab, _ = self.build_tab()
        page = SimpleNamespace(launch_url=AsyncMock())
        asyncio.run(tab.on_open_repository(SimpleNamespace(page=page)))
        page.launch_url.assert_awaited_once_with(
            "https://github.com/CaioFerreiraa/IRIS-virtual-assistant-sandbox"
        )

    def test_folder_picker_starts_in_installed_and_preserves_cancelled_input(self) -> None:
        self.installed.mkdir()
        tab, _ = self.build_tab()
        page = SimpleNamespace(services=[])
        event = SimpleNamespace(page=page)
        tab.folder_picker = SimpleNamespace(
            get_directory_path=AsyncMock(return_value=str(self.root))
        )
        asyncio.run(tab.on_select_folder(event))
        self.assertEqual(str(self.root), tab.external_path_field.value)
        tab.folder_picker.get_directory_path.assert_awaited_once_with(
            dialog_title="Selecionar pasta do módulo",
            initial_directory=str(self.installed),
        )
        tab.folder_picker.get_directory_path.return_value = None
        asyncio.run(tab.on_select_folder(event))
        self.assertEqual(str(self.root), tab.external_path_field.value)
        self.assertEqual(1, len(page.services))

    def test_create_module_adds_static_diagnostic_without_resyncing(self) -> None:
        tab, registry = self.build_tab()
        tab.public_key_field.value = "community.hello"
        tab.name_field.value = "Olá comunidade"

        with patch(
            "ui.settings.module_developer_tab.get_module_registry_state",
            return_value=ModuleRegistryState(),
        ):
            tab.on_create_module()

        self.assertTrue((self.installed / "community_hello" / "module.json").is_file())
        self.assertEqual(0, registry.sync_count)
        self.assertIn("Olá comunidade", _collect_text_values(tab.diagnostics))
        self.assertEqual("success", self.toaster.notifications[-1][0])

    def test_validate_folder_is_static_and_accepts_unimportable_runtime(self) -> None:
        unsafe = create_module_folder(
            self.root,
            "unsafe",
            build_manifest("community.unsafe"),
            main_source='raise RuntimeError("não importar")\n',
        )
        tab, _ = self.build_tab()
        tab.external_path_field.value = str(unsafe)

        tab.on_validate_folder()

        self.assertTrue(tab.external_result.visible)
        self.assertIn("Válido", _collect_text_values(tab.external_result))

    def test_resync_shows_runtime_failure_and_restores_button(self) -> None:
        folder = create_module_folder(
            self.installed,
            "broken",
            build_manifest("community.broken"),
        )
        state = ModuleRegistryState(
            invalid_modules=(
                InvalidModuleInfo(
                    folder_name=folder.name,
                    message="Falha ao importar o runtime.",
                    log_path="logs/module_errors.log",
                    module_public_key="community.broken",
                ),
            )
        )
        tab, registry = self.build_tab(registry_state=state)

        tab.on_synchronize_modules()

        self.assertEqual(1, registry.sync_count)
        self.assertFalse(tab.syncing)
        self.assertFalse(tab.sync_button.disabled)
        texts = _collect_text_values(tab.diagnostics)
        self.assertIn("Falha ao importar o runtime.", texts)
        self.assertIn("Log técnico: logs/module_errors.log", texts)
        self.assertEqual("warning", self.toaster.notifications[-1][0])

    def test_refresh_reuses_last_registry_diagnostics(self) -> None:
        folder = create_module_folder(
            self.installed,
            "runtime_error",
            build_manifest("community.runtime-error"),
        )
        state = ModuleRegistryState(
            invalid_modules=(
                InvalidModuleInfo(
                    folder_name=folder.name,
                    message="Erro preservado do registry.",
                    log_path="",
                ),
            )
        )
        tab, _ = self.build_tab()

        with patch(
            "ui.settings.module_developer_tab.get_module_registry_state",
            return_value=state,
        ):
            tab.refresh_diagnostics()

        self.assertIn(
            "Erro preservado do registry.",
            _collect_text_values(tab.diagnostics),
        )

    def test_home_replaces_module_options_without_rebuilding_view(self) -> None:
        state = HomeViewState(
            [
                {
                    "module_id": 1,
                    "path": "Antigo",
                    "is_executable": True,
                    "icon": "history",
                }
            ]
        )
        root = state.build()
        state.dropdowns.selected_module_id = 1
        state.dropdowns.selected_module_path = "Antigo"

        state.replace_module_options(
            [
                {
                    "module_id": 2,
                    "path": "Novo",
                    "is_executable": True,
                    "icon": "extension",
                }
            ]
        )

        self.assertIs(root, state.controls.root)
        self.assertEqual("Novo", state.module_options[0]["path"])
        self.assertIsNone(state.dropdowns.selected_module_id)
        self.assertEqual("explore", state.controls.module_icon.value)


def _collect_text_values(control: ft.Control) -> list[str]:
    values: list[str] = []
    if isinstance(control, ft.Text):
        values.append(str(control.value))
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        values.extend(_collect_text_values(content))
    for child in getattr(control, "controls", ()) or ():
        if isinstance(child, ft.Control):
            values.extend(_collect_text_values(child))
    return values


if __name__ == "__main__":
    unittest.main()
