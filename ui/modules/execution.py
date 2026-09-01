from __future__ import annotations

import json

import flet as ft

from services.module_service import (
    reset_http_request_definition,
    save_auto_start_preference,
    save_http_request_definition,
    save_module_settings,
)
from ui.shared.components.result_card import build_result_card


class ModuleExecutionMixin:
    def on_save_settings(self, event: ft.ControlEvent) -> None:
        del event
        try:
            values = {
                key: field.value or ""
                for key, field in self.variable_fields.items()
            }
            save_module_settings(
                int(self.detail["id"]),
                self.custom_call_name_field.value,
                values,
                self.session_factory,
            )
        except Exception as error:
            self._show_error(str(error))
            return

        custom_value = (self.custom_call_name_field.value or "").strip() or "-"
        self._set_model_value("Nome de chamada personalizado", custom_value)
        self._reset_settings_save_state()
        self._show_success("Configurações salvas.")

    def on_auto_start_change(self, event: ft.ControlEvent) -> None:
        enabled = bool(event.control.value)
        try:
            save_auto_start_preference(
                int(self.detail["id"]),
                enabled,
                self.session_factory,
            )
        except Exception as error:
            event.control.value = not enabled
            self._update_if_mounted(event.control)
            self._show_error(str(error))
            return
        self.detail["auto_start_enabled"] = enabled
        self._set_model_value("Iniciar com a IRIS", "Sim" if enabled else "Não")
        self._show_success(
            "Preferência de inicialização atualizada para a próxima abertura da IRIS."
        )

    def on_execute(self, event: ft.ControlEvent) -> None:
        del event
        if self.is_executing:
            return
        argument = None
        if self.http_request is not None:
            if self._current_execution_values() != self.execution_state_saved:
                if not self._save_execution_definition(show_feedback=False):
                    return
            if bool(self.http_argument_enabled_switch.value):
                argument = self.argument_field.value or ""
        elif self.argument_field is not None and not self.argument_field.disabled:
            argument = (self.argument_field.value or "").strip()
            if not argument:
                self.on_select_tab("execution")
                self._show_error("Informe o argumento antes de executar o módulo.")
                return

        self._show_execution_result(
            "executando",
            {"status": "executando", "message": "Aguardando retorno do módulo."},
        )
        self._set_execute_loading(True)
        try:
            page = self.execute_button.page
        except RuntimeError:
            page = None
        if page is None:
            try:
                result = self.home_service.execute_module(
                    int(self.detail["id"]),
                    argument,
                )
                self._apply_execution_result(result, None)
            except Exception as error:
                self._apply_execution_result(None, error)
            return
        page.run_thread(
            self._execute_background,
            page,
            argument,
        )

    def on_save_execution(self, event: ft.ControlEvent | None) -> None:
        del event
        self._save_execution_definition(show_feedback=True)

    def _save_execution_definition(self, *, show_feedback: bool) -> bool:
        if self.http_request is None or self.argument_field is None:
            return True
        try:
            values = self._build_http_request_values()
            saved_request = save_http_request_definition(
                int(self.detail["id"]),
                values,
                self.session_factory,
            )
        except Exception as error:
            self._show_error(str(error))
            return False

        self.http_request = saved_request
        self.detail["http_request"] = saved_request
        self._reset_execution_save_state()
        if show_feedback:
            self._show_success("Requisição HTTP salva.")
        return True

    def _build_http_request_values(self) -> dict[str, object]:
        values = self._current_execution_values()
        body_mode = str(values["body_mode"])
        body_content_text = str(values["body_content"])
        if body_mode == "form_urlencoded":
            try:
                body_content: object = json.loads(body_content_text)
            except json.JSONDecodeError as error:
                raise ValueError(
                    "O conteúdo form_urlencoded deve conter uma lista JSON válida."
                ) from error
        else:
            body_content = body_content_text

        return {
            "method": values["method"],
            "url": values["url"],
            "argument_enabled": values["argument_enabled"],
            "argument": values["argument"],
            "params_json": values["params_json"],
            "authorization_json": values["authorization_json"],
            "headers_json": values["headers_json"],
            "body_json": json.dumps(
                {"mode": body_mode, "content": body_content},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "scripts_json": json.dumps(
                {
                    "pre_request": values["pre_request"],
                    "post_response": values["post_response"],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }

    def on_restore_http_request(self, event: ft.ControlEvent | None) -> None:
        del event
        try:
            restored_request = reset_http_request_definition(
                int(self.detail["id"]),
                self.session_factory,
            )
        except Exception as error:
            self._show_error(str(error))
            return

        self.http_request = restored_request
        self.detail["http_request"] = restored_request
        argument_enabled = bool(restored_request["argument_enabled"])
        self.argument_explanation = (
            "Informe a string que substituirá {{argument}} na requisição."
            if argument_enabled
            else "Este módulo não utiliza argumento de execução."
        )
        self.argument_field.value = str(restored_request.get("argument") or "")
        self.argument_field.disabled = (
            not bool(self.detail["is_available"])
            or not argument_enabled
        )
        self.argument_field.helper = self.argument_explanation
        self.argument_field.tooltip = self.argument_explanation
        restored_tab = self._build_execution_tab()
        self.tab_views["execution"] = restored_tab
        if self.active_tab == "execution":
            self.tab_content.content = restored_tab
            self._update_if_mounted(self.tab_content)
        self._show_success("Requisição restaurada a partir do module.json.")

    def _execute_background(
        self,
        page: ft.Page,
        argument: str | None,
    ) -> None:
        try:
            result = self.home_service.execute_module(
                int(self.detail["id"]),
                argument,
            )
            page.run_task(self._finish_execution, result, None)
        except Exception as error:
            page.run_task(self._finish_execution, None, error)

    async def _finish_execution(
        self,
        result: dict | None,
        error: Exception | None,
    ) -> None:
        self._apply_execution_result(result, error)

    def _apply_execution_result(
        self,
        result: dict | None,
        error: Exception | None,
    ) -> None:
        if error is not None:
            self._show_execution_result(
                "erro",
                {
                    "success": False,
                    "error": str(error) or "Não foi possível executar o módulo.",
                },
            )
            self._show_error(str(error) or "Não foi possível executar o módulo.")
        elif result is not None and result.get("success", True):
            self._show_execution_result("sucesso", result)
            self._show_success(
                self._result_message(result) or "Módulo executado com sucesso."
            )
        else:
            self._show_execution_result("erro", result or {"success": False})
            self._show_error(
                self._result_message(result or {}) or "O módulo retornou erro."
            )
        self._set_execute_loading(False)
        self._refresh_logs()

    def _build_execution_result_card(self) -> ft.Container:
        return ft.Container(
            opacity=0,
            offset=ft.Offset(0, -0.25),
            animate_opacity=180,
            animate_offset=240,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

    def _show_execution_result(
        self,
        status: str,
        result: dict[str, object],
    ) -> None:
        self.execution_result_card.content = build_result_card(status, result)
        self.execution_result_card.opacity = 1
        self.execution_result_card.offset = ft.Offset(0, 0)
        self._update_if_mounted(self.execution_result_card)

    def _set_execute_loading(self, is_loading: bool) -> None:
        self.is_executing = is_loading
        self.execute_button.disabled = is_loading
        self.execute_button.content = (
            ft.Row(
                tight=True,
                spacing=8,
                controls=[
                    ft.ProgressRing(
                        width=16,
                        height=16,
                        stroke_width=2,
                        color=ft.Colors.WHITE,
                    ),
                    ft.Text("Executando..."),
                ],
            )
            if is_loading
            else ft.Text("Executar")
        )
        self._update_if_mounted(self.execute_button)

    def _set_model_value(self, label: str, value: str) -> None:
        control = self.model_value_controls.get(label)
        if control is None:
            return
        control.value = value
        control.tooltip = value
        self._update_if_mounted(control)

    def _result_message(self, result: dict) -> str:
        if "message" in result:
            return str(result["message"])
        if "result" in result:
            return str(result["result"])
        if "opened" in result:
            return f"URL aberta: {result['opened']}"
        return ""

    def _show_success(self, message: str) -> None:
        if self.toaster_handler is not None:
            self.toaster_handler.show_success(message)

    def _show_error(self, message: str) -> None:
        if self.toaster_handler is not None:
            self.toaster_handler.show_error(message)

    def _update_if_mounted(self, control: ft.Control) -> None:
        try:
            if control.page is not None:
                control.update()
        except RuntimeError:
            return
