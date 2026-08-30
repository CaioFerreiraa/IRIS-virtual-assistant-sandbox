from __future__ import annotations

import flet as ft

from services.module_service import save_auto_start_preference, save_module_settings
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
        if self.argument_field is not None:
            argument = (self.argument_field.value or "").strip()
            if not argument:
                self.on_select_tab("settings")
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
