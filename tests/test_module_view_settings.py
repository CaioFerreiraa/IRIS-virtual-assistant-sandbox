import tempfile
import unittest
from pathlib import Path

import flet as ft
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base, enable_sqlite_foreign_keys
from database.models import Module
from services.module_service import get_module_detail
from ui.modules.views.module_view_state import ModuleViewState


class ModuleViewSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        database_path = Path(self.temporary_directory.name) / "module-view.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        self.addCleanup(self.engine.dispose)
        enable_sqlite_foreign_keys(self.engine)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        db = self.session_factory()
        try:
            module = Module(
                module_public_key="test.view",
                name="Módulo de teste",
                call_name="teste",
                is_executable=True,
                is_available=True,
                request_method="GET",
                request_url="https://example.com",
            )
            db.add(module)
            db.commit()
            self.module_id = module.id
        finally:
            db.close()

    def _build_state(self, *, has_arguments: bool = False) -> ModuleViewState:
        detail = get_module_detail(self.module_id, self.session_factory)
        self.assertIsNotNone(detail)
        detail["has_arguments"] = has_arguments
        return ModuleViewState(detail, None, self.session_factory)

    def test_model_data_uses_every_column_from_module_model(self) -> None:
        detail = get_module_detail(self.module_id, self.session_factory)

        field_names = [field["name"] for field in detail["model_data"]]

        self.assertEqual(
            [column.key for column in Module.__table__.columns],
            field_names,
        )

    def test_model_data_is_last_card_and_keeps_distinct_tooltips(self) -> None:
        state = self._build_state()
        settings = state._build_settings_tab()
        content_column = settings.controls[0]
        model_data_card = content_column.controls[-2]

        self.assertIn("Dados do módulo", _collect_text_values(model_data_card))
        first_wrapper = model_data_card.content.controls[1].controls[0]
        field = first_wrapper.content.controls[0].content
        info = first_wrapper.content.controls[1]
        self.assertEqual(str(self.module_id), field.tooltip)
        self.assertIn(
            "Identificador numérico interno",
            info.tooltip.message,
        )

    def test_argument_updates_saved_and_edited_state(self) -> None:
        state = self._build_state(has_arguments=True)
        state._build_settings_tab()

        self.assertIsNone(state.module_state_edited)
        state.argument_field.value = "Campinas"
        state.on_settings_form_change()

        self.assertEqual("", state.module_state_saved["argument"])
        self.assertEqual("Campinas", state.module_state_edited["argument"])
        self.assertTrue(state.settings_save_bar.visible)

        state.argument_field.value = ""
        state.on_settings_form_change()
        self.assertFalse(state.settings_save_bar.visible)

    def test_execution_result_card_shows_status_and_full_body(self) -> None:
        state = self._build_state()

        state._show_execution_result(
            "sucesso",
            {"success": True, "result": {"city": "Campinas"}},
        )

        texts = _collect_text_values(state.execution_result_card)
        self.assertEqual(180, state.execution_result_card.height)
        self.assertIn("Sucesso", texts)
        self.assertIn("Corpo de retorno", texts)
        self.assertTrue(any('"city": "Campinas"' in text for text in texts))

    def test_header_status_has_same_height_as_execute_button(self) -> None:
        state = self._build_state()

        status_chip = state._build_header_trailing().controls[1]

        self.assertEqual(state.execute_button.height, status_chip.height)


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
