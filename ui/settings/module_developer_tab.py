from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import flet as ft

from services.module_development_service import (
    ModuleDevelopmentService,
    ModuleScaffoldError,
    ModuleValidationReport,
)
from services.module_registry_service import ModuleRegistryService
from services.module_registry_state import (
    InvalidModuleInfo,
    ModuleRegistryState,
    get_module_registry_state,
)
from ui.shared.components.form_controls import (
    build_dropdown,
    build_primary_button,
    build_secondary_button,
    build_text_field,
)
from ui.shared.components.toaster_handler import ToasterHandler
from ui.shared.components.custom_dialog import show_custom_dialog
from ui.theme.colors import (
    BORDER,
    BLUE_GREY,
    CANCEL,
    PASTEL_DARK_GREEN,
    PASTEL_DARK_PURPLE,
    PASTEL_YELLOW,
    SURFACE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


RegistryFactory = Callable[[], ModuleRegistryService]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_REPOSITORY_URL = "https://github.com/CaioFerreiraa/IRIS-virtual-assistant-sandbox"


class _DeveloperContent(ft.Column):
    def __init__(self, tab: ModuleDeveloperTab, **kwargs) -> None:
        super().__init__(**kwargs)
        self.tab = tab

    def did_mount(self) -> None:
        self.page.run_thread(self.tab.refresh_diagnostics)


class ModuleDeveloperTab:
    def __init__(
        self,
        toaster_handler: ToasterHandler | None,
        development_service: ModuleDevelopmentService | None = None,
        registry_factory: RegistryFactory | None = None,
    ) -> None:
        self.toaster_handler = toaster_handler
        self.development_service = development_service or ModuleDevelopmentService()
        self.registry_factory = registry_factory or (
            lambda: ModuleRegistryService(
                installed_modules_dir=self.development_service.installed_modules_dir
            )
        )
        self.public_key_field = build_text_field(
            "Chave pública",
            "",
            helper="Exemplo: community.hello",
        )
        self.name_field = build_text_field("Nome exibido", "")
        self.kind_dropdown = build_dropdown(
            "Tipo",
            "python",
            (("python", "Python"), ("http", "HTTP declarativo")),
            width=210,
            expand=False,
        )
        self.external_path_field = build_text_field(
            "Pasta local",
            "",
            helper="Valida module.json e arquivos sem importar o runtime.",
        )
        self.external_result = ft.Container(visible=False)
        self.folder_picker = ft.FilePicker()
        self.diagnostics = ft.Column(spacing=10)
        self.sync_button = build_primary_button(
            "Ressincronizar módulos",
            self.on_synchronize_modules,
        )
        self.refresh_button = build_secondary_button(
            "Atualizar diagnóstico",
            self.on_refresh_diagnostics,
        )
        self.syncing = False

    def build(self) -> ft.Column:
        self.diagnostics.controls = [ft.Text("Carregando diagnóstico...")]
        return _DeveloperContent(
            self,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=16,
            controls=[
                ft.Text("Módulos locais", size=28, weight=ft.FontWeight.W_700,
                        color=TEXT_PRIMARY),
                self._build_onboarding_card(),
                self._build_create_card(),
                self._build_validate_card(),
                self._build_warning_card(),
                self._build_diagnostics_card(),
            ],
        )

    def _build_onboarding_card(self) -> ft.Container:
        return self._build_section(
            "Crie seu primeiro módulo",
            "Módulos adicionam novas capacidades à IRIS. Aqui você pode criar "
            "uma estrutura inicial, validar seus arquivos e carregar o módulo "
            "para testá-lo na aplicação.",
            ft.Column(
                spacing=12,
                controls=[
                    ft.Text("1. Crie a estrutura — escolha Python ou HTTP e preencha os dados.",
                            color=TEXT_PRIMARY),
                    ft.Text("2. Implemente e valide — edite os arquivos no seu editor e confira o diagnóstico.",
                            color=TEXT_PRIMARY),
                    ft.Text("3. Teste e contribua — ressincronize o código revisado, teste a ação e prepare sua contribuição.",
                            color=TEXT_PRIMARY),
                    ft.Row(scroll=ft.ScrollMode.AUTO, spacing=10, controls=[
                        build_secondary_button("Guia de módulos", self.on_open_module_guide),
                        build_secondary_button("Como contribuir", self.on_open_contributing),
                        build_secondary_button("Repositório do projeto", self.on_open_repository),
                    ]),
                ],
            ),
        )

    def on_open_module_guide(self, event: ft.ControlEvent) -> None:
        self._open_local_document(event.page, PROJECT_ROOT / "documentation/module-development.md")

    def on_open_contributing(self, event: ft.ControlEvent) -> None:
        self._open_local_document(event.page, PROJECT_ROOT / "CONTRIBUTING.md")

    async def on_open_repository(self, event: ft.ControlEvent) -> None:
        await event.page.launch_url(PUBLIC_REPOSITORY_URL)

    def _open_local_document(self, page: ft.Page, path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            self._show_error("O documento não foi encontrado nesta instalação.", "Documentação")
            return

        async def on_link(event: ft.ControlEvent) -> None:
            target = str(event.data or "")
            if target.startswith(("https://", "http://")):
                await event.page.launch_url(target)
                return
            linked_path = (path.parent / target.split("#", 1)[0]).resolve()
            if linked_path.is_relative_to(PROJECT_ROOT) and linked_path.suffix.lower() == ".md":
                dialog.open = False
                self._open_local_document(event.page, linked_path)

        dialog = show_custom_dialog(
            page,
            "Guia de módulos" if path.name == "module-development.md" else "Como contribuir",
            width=780,
            alignment=ft.Alignment.CENTER,
            inset_padding=ft.Padding.all(24),
            content=ft.Container(
                width=780,
                height=500,
                content=ft.Column(scroll=ft.ScrollMode.AUTO, controls=[
                    ft.Markdown(content, selectable=True,
                                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                                on_tap_link=on_link),
                ]),
            ),
        )

    def _build_warning_card(self) -> ft.Container:
        return ft.Container(
            padding=16,
            bgcolor=PASTEL_YELLOW,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            content=ft.Column(
                tight=True,
                spacing=8,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(
                                ft.Icons.DEVELOPER_MODE_ROUNDED,
                                color=PASTEL_DARK_PURPLE,
                            ),
                            ft.Text(
                                "Ferramentas de desenvolvimento",
                                size=16,
                                weight=ft.FontWeight.W_700,
                                color=TEXT_PRIMARY,
                            ),
                        ],
                    ),
                    ft.Text(
                        "Validar uma pasta não executa o módulo. Ressincronizar "
                        "importa entry points Python no processo da IRIS; use "
                        "somente código revisado.",
                        size=13,
                        color=TEXT_PRIMARY,
                    ),
                    ft.Row(
                        spacing=10,
                        controls=[self.sync_button, self.refresh_button],
                    ),
                ],
            ),
        )

    def _build_create_card(self) -> ft.Container:
        return self._build_section(
            "Criar módulo local",
            "Gera uma pasta inicial em modules/installed sem substituir arquivos existentes.",
            ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    ft.ResponsiveRow(
                        spacing=12,
                        run_spacing=12,
                        controls=[
                            ft.Container(
                                col={"xs": 12, "md": 5},
                                content=self.public_key_field,
                            ),
                            ft.Container(
                                col={"xs": 12, "md": 5},
                                content=self.name_field,
                            ),
                            ft.Container(
                                col={"xs": 12, "md": 2},
                                content=self.kind_dropdown,
                            ),
                        ],
                    ),
                    ft.Row(
                        controls=[
                            build_primary_button(
                                "Criar módulo",
                                self.on_create_module,
                            )
                        ]
                    ),
                ],
            ),
        )

    def _build_validate_card(self) -> ft.Container:
        return self._build_section(
            "Validar pasta local",
            "Confere um módulo dentro ou fora de modules/installed sem importar main.py.",
            ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    ft.Row(
                        spacing=10,
                        controls=[
                            self.external_path_field,
                            build_secondary_button(
                                "Selecionar pasta",
                                self.on_select_folder,
                            ),
                            build_secondary_button(
                                "Validar pasta",
                                self.on_validate_folder,
                            ),
                        ],
                    ),
                    self.external_result,
                ],
            ),
        )

    def _build_diagnostics_card(self) -> ft.Container:
        return self._build_section(
            "Diagnóstico de modules/installed",
            "A lista combina a validação segura atual com falhas da última ressincronização.",
            self.diagnostics,
        )

    def _build_section(
        self,
        title: str,
        description: str,
        content: ft.Control,
    ) -> ft.Container:
        return ft.Container(
            padding=18,
            bgcolor=BLUE_GREY,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            content=ft.Column(
                tight=True,
                spacing=14,
                controls=[
                    ft.Column(
                        tight=True,
                        spacing=4,
                        controls=[
                            ft.Text(
                                title,
                                size=16,
                                weight=ft.FontWeight.W_700,
                                color=TEXT_PRIMARY,
                            ),
                            ft.Text(description, size=13, color=TEXT_SECONDARY),
                        ],
                    ),
                    content,
                ],
            ),
        )

    def on_create_module(self, event: ft.ControlEvent | None = None) -> None:
        try:
            target = self.development_service.create_module(
                str(self.public_key_field.value or ""),
                str(self.name_field.value or ""),
                kind=str(self.kind_dropdown.value or "python"),
            )
        except (ModuleScaffoldError, OSError, ValueError) as error:
            self._show_error(str(error), "Não foi possível criar o módulo")
            return

        self.public_key_field.value = ""
        self.name_field.value = ""
        self.refresh_diagnostics()
        self._update_if_mounted(self.public_key_field)
        self._update_if_mounted(self.name_field)
        self._show_success(
            f"Módulo criado em {target}. Revise os arquivos antes de ressincronizar.",
            "Módulo local criado",
        )

    async def on_select_folder(self, event: ft.ControlEvent) -> None:
        page = event.page
        if self.folder_picker not in page.services:
            page.services.append(self.folder_picker)
        initial_directory = self.development_service.installed_modules_dir
        if not initial_directory.is_dir():
            initial_directory = initial_directory.parent.parent
        try:
            selected = await self.folder_picker.get_directory_path(
                dialog_title="Selecionar pasta do módulo",
                initial_directory=str(initial_directory),
            )
        except Exception as error:
            self._show_error(str(error), "Não foi possível selecionar a pasta")
            return
        if selected:
            self.external_path_field.value = selected
            self._update_if_mounted(self.external_path_field)

    def on_validate_folder(self, event: ft.ControlEvent | None = None) -> None:
        raw_path = str(self.external_path_field.value or "").strip()
        if not raw_path:
            self._show_error("Informe a pasta que contém module.json.", "Validação")
            return
        report = self.development_service.validate_module(Path(raw_path))
        self.external_result.content = self._build_report_card(report)
        self.external_result.visible = True
        self._update_if_mounted(self.external_result)

    def on_refresh_diagnostics(self, event: ft.ControlEvent | None = None) -> None:
        if event is not None:
            event.page.run_thread(self.refresh_diagnostics)
        else:
            self.refresh_diagnostics()

    def on_synchronize_modules(self, event: ft.ControlEvent | None = None) -> None:
        if self.syncing:
            return
        self._set_syncing(True)
        page = event.page if event is not None else None
        if page is None:
            self._synchronize_modules()
            return
        page.run_thread(self._synchronize_modules)

    def _synchronize_modules(self) -> None:
        try:
            state = self.registry_factory().sync()
        except Exception as error:
            self._show_error(
                str(error).strip() or "A ressincronização falhou.",
                "Erro ao ressincronizar módulos",
            )
        else:
            self.refresh_diagnostics(state)
            invalid_count = len(state.invalid_modules)
            if invalid_count:
                self._show_warning(
                    f"Ressincronização concluída com {invalid_count} módulo(s) inválido(s).",
                    "Módulos atualizados",
                )
            else:
                self._show_success(
                    "Módulos ressincronizados. A barra lateral será atualizada "
                    "na próxima navegação.",
                    "Módulos atualizados",
                )
        finally:
            self._set_syncing(False)

    def refresh_diagnostics(
        self,
        registry_state: ModuleRegistryState | None = None,
    ) -> None:
        registry_state = registry_state or get_module_registry_state()
        reports = self.development_service.list_installed_modules()
        invalid_by_folder = {
            item.folder_name: item
            for item in registry_state.invalid_modules
        }
        controls = [
            self._build_report_card(
                report,
                invalid_by_folder.get(report.folder.name),
            )
            for report in reports
        ]
        if not controls:
            controls = [
                ft.Container(
                    padding=16,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(
                        "Nenhuma pasta foi encontrada em modules/installed.",
                        color=TEXT_SECONDARY,
                    ),
                )
            ]
        self.diagnostics.controls = controls
        self._update_if_mounted(self.diagnostics)

    def _build_report_card(
        self,
        report: ModuleValidationReport,
        registry_error: InvalidModuleInfo | None = None,
    ) -> ft.Container:
        is_valid = report.is_valid and registry_error is None
        color = PASTEL_DARK_GREEN if is_valid else CANCEL
        status = "Válido" if is_valid else "Com problema"
        message = registry_error.message if registry_error is not None else report.message
        controls: list[ft.Control] = [
            ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED
                        if is_valid
                        else ft.Icons.ERROR_OUTLINE_ROUNDED,
                        color=color,
                        size=20,
                    ),
                    ft.Text(
                        report.name or report.module_public_key or report.folder.name,
                        expand=True,
                        size=14,
                        weight=ft.FontWeight.W_700,
                        color=TEXT_PRIMARY,
                    ),
                    ft.Text(status, size=12, color=color),
                ],
            ),
            ft.Text(message, size=12, color=TEXT_PRIMARY, selectable=True),
            ft.Text(
                str(report.folder),
                size=11,
                color=TEXT_SECONDARY,
                selectable=True,
                font_family="Consolas",
            ),
        ]
        if registry_error is not None and registry_error.log_path:
            controls.append(
                ft.Text(
                    f"Log técnico: {registry_error.log_path}",
                    size=11,
                    color=TEXT_SECONDARY,
                    selectable=True,
                    font_family="Consolas",
                )
            )
        return ft.Container(
            padding=14,
            bgcolor=SURFACE,
            border=ft.Border.all(1, color),
            border_radius=8,
            content=ft.Column(tight=True, spacing=7, controls=controls),
        )

    def _set_syncing(self, syncing: bool) -> None:
        self.syncing = syncing
        self.sync_button.disabled = syncing
        self.sync_button.content = ft.Row(
            tight=True,
            spacing=8,
            controls=(
                [
                    ft.ProgressRing(width=16, height=16, stroke_width=2),
                    ft.Text("Ressincronizando..."),
                ]
                if syncing
                else [ft.Text("Ressincronizar módulos")]
            ),
        )
        self._update_if_mounted(self.sync_button)

    def _show_success(self, message: str, title: str) -> None:
        if self.toaster_handler is not None:
            self.toaster_handler.show_success(message, title=title)

    def _show_warning(self, message: str, title: str) -> None:
        if self.toaster_handler is not None:
            self.toaster_handler.show_warning(message, title=title)

    def _show_error(self, message: str, title: str) -> None:
        if self.toaster_handler is not None:
            self.toaster_handler.show_error(message, title=title)

    def _update_if_mounted(self, control: ft.Control) -> None:
        try:
            if control.page is not None:
                control.update()
        except RuntimeError:
            return
