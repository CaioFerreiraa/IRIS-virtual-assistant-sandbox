import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import flet as ft
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base, enable_sqlite_foreign_keys
from database.models import Module, ModuleHttpRequest
from services.module_service import get_module_detail
from ui.modules.views.module_view_state import ModuleViewState
from ui.shared.components.result_card import MIN_RESULT_CARD_HEIGHT
from ui.theme.colors import GREY_200, TEXT_PRIMARY


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

    def test_argument_does_not_participate_in_settings_snapshot(self) -> None:
        state = self._build_state(has_arguments=True)
        state._build_settings_tab()

        self.assertIsNone(state.module_state_edited)
        self.assertNotIn("argument", state.module_state_saved)
        self.assertIsNone(state.argument_field.on_change)

    def test_execution_result_card_shows_status_and_full_body(self) -> None:
        state = self._build_state()

        state._show_execution_result(
            "sucesso",
            {"success": True, "result": {"city": "Campinas"}},
        )

        texts = _collect_text_values(state.execution_result_card)
        self.assertEqual(180, state.execution_result_card.content.height)
        self.assertIn("Sucesso", texts)
        self.assertIn("Corpo de retorno", texts)
        self.assertTrue(any('"city": "Campinas"' in text for text in texts))

    def test_execution_result_card_can_be_resized_to_header_height(self) -> None:
        state = self._build_state()
        state._show_execution_result("sucesso", {"success": True})
        result_card = state.execution_result_card.content
        resize_handle = result_card.content.controls[1]

        resize_handle.on_vertical_drag_update(
            SimpleNamespace(primary_delta=-1000, local_delta=None)
        )

        self.assertEqual(MIN_RESULT_CARD_HEIGHT, result_card.height)

        resize_handle.on_vertical_drag_update(
            SimpleNamespace(primary_delta=80, local_delta=None)
        )
        self.assertEqual(MIN_RESULT_CARD_HEIGHT + 80, result_card.height)

    def test_header_status_has_same_height_as_execute_button(self) -> None:
        state = self._build_state()

        status_chip = state._build_header_trailing().controls[1]

        self.assertEqual(state.execute_button.height, status_chip.height)

    def test_available_module_without_runtime_status_is_offline(self) -> None:
        with patch(
            "services.module_service.get_module_registry_state",
            return_value=SimpleNamespace(
                runtime_statuses={},
                invalid_modules=(),
            ),
        ):
            state = self._build_state()

        self.assertEqual("offline", state.detail["status"])

    def test_execution_tab_appears_only_for_executable_modules(self) -> None:
        executable_state = self._build_state()
        self.assertIn(
            "execution",
            [tab[0] for tab in executable_state.tab_definitions],
        )

        db = self.session_factory()
        try:
            module = Module(
                module_public_key="test.organizational",
                name="Organizacional",
                call_name="organizacional",
                is_executable=False,
                is_available=True,
            )
            db.add(module)
            db.commit()
            module_id = module.id
        finally:
            db.close()
        detail = get_module_detail(module_id, self.session_factory)
        organizational_state = ModuleViewState(
            detail,
            None,
            self.session_factory,
        )
        self.assertNotIn(
            "execution",
            [tab[0] for tab in organizational_state.tab_definitions],
        )

    def test_disabled_http_argument_field_shows_explanation(self) -> None:
        self._add_http_request(argument_enabled=False, argument="anterior")

        state = self._build_state()

        self.assertTrue(state.argument_field.disabled)
        self.assertEqual("anterior", state.argument_field.value)
        self.assertEqual(
            "Este módulo não utiliza argumento de execução.",
            state.argument_field.helper,
        )

    def test_unavailable_http_inputs_use_disabled_style(self) -> None:
        self._add_http_request(argument_enabled=True, argument="Campinas")
        db = self.session_factory()
        try:
            module = db.get(Module, self.module_id)
            module.is_available = False
            module.validation_error = "Configuração inválida."
            db.commit()
        finally:
            db.close()
        state = self._build_state()
        state._build_execution_tab()

        for field in (state.http_method_field, state.http_url_field):
            self.assertTrue(field.disabled)
            self.assertEqual(GREY_200, field.bgcolor)
            self.assertEqual(TEXT_PRIMARY, field.border_color)
            self.assertEqual(TEXT_PRIMARY, field.text_style.color)

    def test_enabled_http_argument_loads_last_value(self) -> None:
        self._add_http_request(argument_enabled=True, argument="Campinas")

        state = self._build_state()

        self.assertFalse(state.argument_field.disabled)
        self.assertEqual("Campinas", state.argument_field.value)
        execution_tab = state._build_execution_tab()
        texts = _collect_text_values(execution_tab)
        self.assertIn("Nenhum parâmetro configurado.", texts)
        self.assertIn("Sem autenticação", texts)
        self.assertIn("Scripts são exibidos, mas não são executados nesta versão.", texts)

    def test_argument_card_is_first_and_uses_full_width(self) -> None:
        state = self._build_state(has_arguments=True)

        execution_tab = state._build_execution_tab()
        content_column = execution_tab.controls[0]
        argument_card = content_column.controls[0]

        self.assertEqual(float("inf"), argument_card.width)
        self.assertIn("Argumento da execução", _collect_text_values(argument_card))
        self.assertNotIn("Execução Python", _collect_text_values(execution_tab))

    def test_argument_card_remains_first_for_unavailable_module(self) -> None:
        db = self.session_factory()
        try:
            module = db.get(Module, self.module_id)
            module.is_available = False
            module.validation_error = "Configuração inválida."
            db.commit()
        finally:
            db.close()
        state = self._build_state(has_arguments=True)

        execution_tab = state._build_execution_tab()
        content_column = execution_tab.controls[0]

        self.assertIn(
            "Argumento da execução",
            _collect_text_values(content_column.controls[0]),
        )
        self.assertIn(
            "Configuração inválida.",
            _collect_text_values(content_column.controls[1]),
        )

    def test_http_argument_change_shows_save_bar_and_persists_value(self) -> None:
        self._add_http_request(argument_enabled=True, argument="Campinas")
        state = self._build_state()
        state._build_execution_tab()

        self.assertFalse(state.execution_save_bar.is_visible)
        state.argument_field.value = "Recife"
        state.on_execution_form_change()

        self.assertTrue(state.execution_save_bar.is_visible)
        state.on_save_execution(None)
        self.assertFalse(state.execution_save_bar.is_visible)

        db = self.session_factory()
        try:
            request = (
                db.query(ModuleHttpRequest)
                .filter(ModuleHttpRequest.module_id == self.module_id)
                .one()
            )
            self.assertEqual("Recife", request.argument)
        finally:
            db.close()

    def test_http_definition_fields_are_editable_and_saved_together(self) -> None:
        self._add_http_request(argument_enabled=True, argument="Campinas")
        state = self._build_state()
        state._build_execution_tab()

        fields = (
            state.http_method_field,
            state.http_url_field,
            state.http_authorization_field,
            state.http_body_mode_field,
            state.http_body_content_field,
            state.http_pre_request_field,
            state.http_post_response_field,
        )
        self.assertTrue(all(not field.disabled for field in fields))
        self.assertFalse(state.http_url_field.read_only)

        state.http_method_field.value = "POST"
        state.http_url_field.value = "https://api.example.com/search/{{argument}}"
        state.http_authorization_field.value = "none"
        state._add_http_item(None, "headers")
        header = state.http_header_rows[0]
        header["key"].value = "Content-Type"
        header["value"].value = "application/json"
        header["description"].value = "Formato"
        header["enabled"].value = True
        state.http_body_mode_field.value = "raw_json"
        state.http_body_content_field.value = '{"query":"{{argument}}"}'
        state.http_pre_request_field.value = 'console.log("pre")'
        state.http_post_response_field.value = 'console.log("post")'
        state.on_execution_form_change()

        self.assertTrue(state.execution_save_bar.is_visible)
        state.on_save_execution(None)

        db = self.session_factory()
        try:
            request = db.query(ModuleHttpRequest).one()
            self.assertEqual("POST", request.method)
            self.assertEqual(
                "https://api.example.com/search/{{argument}}",
                request.url,
            )
            self.assertIn("Content-Type", request.headers_json)
            self.assertIn("raw_json", request.body_json)
            self.assertIn("console.log", request.scripts_json)
            self.assertTrue(request.is_customized)
        finally:
            db.close()

    def test_http_parameter_rows_can_be_added_and_removed(self) -> None:
        self._add_http_request(argument_enabled=True, argument="Campinas")
        state = self._build_state()
        state._build_execution_tab()

        state._add_http_item(None, "params")

        self.assertEqual(1, len(state.http_param_rows))
        self.assertFalse(state.http_params_empty_text.visible)
        self.assertTrue(state.execution_save_bar.is_visible)

        state._remove_http_item(None, "params", state.http_param_rows[0])

        self.assertEqual([], state.http_param_rows)
        self.assertTrue(state.http_params_empty_text.visible)

    def test_python_argument_remains_transient_without_save_bar(self) -> None:
        state = self._build_state(has_arguments=True)

        state._build_execution_tab()

        self.assertIsNone(state.execution_save_bar)

    def _add_http_request(
        self,
        *,
        argument_enabled: bool,
        argument: str,
    ) -> None:
        db = self.session_factory()
        try:
            db.add(
                ModuleHttpRequest(
                    module_id=self.module_id,
                    method="GET",
                    url="https://api.example.com/items",
                    argument_enabled=argument_enabled,
                    argument=argument,
                )
            )
            db.commit()
        finally:
            db.close()


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
