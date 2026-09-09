from __future__ import annotations

from datetime import datetime

import flet as ft

from database.db import SessionLocal
from services.routine_schedule_service import (
    MONTHLY,
    WEEKDAY_KEYS,
    WEEKDAY_LABELS,
    WEEKLY,
)
from services.routine_service import RoutineService
from ui.shared.components.custom_dialog import custom_dialog
from ui.shared.components.form_controls import (
    build_dropdown,
    build_primary_button,
    build_secondary_button,
    build_text_field,
)
from ui.shared.components.route_content_container import build_route_content_container
from ui.shared.components.table import TableColumn, build_responsive_table
from ui.theme.colors import (
    BLUE_GREY,
    BORDER,
    CANCEL,
    CONFIRM,
    PASTEL_BLUE,
    PASTEL_DARK_PURPLE,
    SURFACE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)


ROUTINE_COLUMNS = (
    TableColumn("name", "Nome", 3),
    TableColumn("schedule", "Agendamento", 4),
    TableColumn("modules", "Módulos", 1),
    TableColumn("next_run", "Próxima", 2),
    TableColumn("last_run", "Última", 2),
    TableColumn("status", "Status", 2),
    TableColumn("actions", "Ações", 2),
)


def build_routines_view(
    *,
    toaster_handler=None,
    session_factory=SessionLocal,
    routine_service: RoutineService | None = None,
) -> ft.Container:
    return RoutinesViewState(
        toaster_handler=toaster_handler,
        routine_service=routine_service or RoutineService(session_factory),
    ).build()


class RoutinesViewState:
    def __init__(self, *, toaster_handler=None, routine_service: RoutineService):
        self.toaster_handler = toaster_handler
        self.routine_service = routine_service
        self.routines: list[dict[str, object]] = []
        self.running_ids: set[int] = set()
        self.content_slot = ft.Container(expand=True)
        self.root: ft.Container | None = None

    def build(self) -> ft.Container:
        self.root = build_route_content_container(
            icon=ft.Icons.AUTORENEW_ROUNDED,
            title="Rotinas",
            subtitle="Crie sequências de módulos e execute-as manualmente ou em horários agendados.",
            trailing=build_primary_button(
                "Nova rotina",
                self.open_create_form,
                height=38,
            ),
            content=self.content_slot,
        )
        self.refresh()
        return self.root

    def refresh(self) -> None:
        self.content_slot.content = ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.ProgressRing(color=BLUE_GREY),
        )
        self._update_if_mounted(self.content_slot)
        try:
            self.routines = self.routine_service.list_routines()
            self.content_slot.content = build_responsive_table(
                columns=ROUTINE_COLUMNS,
                rows=[self._build_row(routine) for routine in self.routines],
                empty_message="Nenhuma rotina cadastrada.",
                row_height=66,
            )
        except Exception as error:
            self.content_slot.content = self._build_error_state(error)
        self._update_if_mounted(self.content_slot)

    def open_create_form(self, event: ft.ControlEvent) -> None:
        self._open_form(event, None)

    def open_edit_form(self, event: ft.ControlEvent, routine_id: int) -> None:
        self._open_form(event, routine_id)

    def on_toggle_active(
        self,
        event: ft.ControlEvent,
        routine_id: int,
    ) -> None:
        switch = event.control
        requested_state = bool(switch.value)
        switch.disabled = True
        self._update_if_mounted(switch)
        try:
            self.routine_service.set_active(routine_id, requested_state)
            self._show(
                "success",
                "Rotina ativada." if requested_state else "Rotina desativada.",
            )
        except Exception as error:
            switch.value = not requested_state
            switch.disabled = False
            self._update_if_mounted(switch)
            self._show("error", str(error))
            return
        self.refresh()

    def execute_now(self, event: ft.ControlEvent, routine_id: int) -> None:
        if routine_id in self.running_ids:
            self._show("warning", "Esta rotina já está em execução.")
            return
        # Capture the page while the clicked button is still mounted. Refreshing
        # the table replaces the row controls and detaches the event source.
        page = getattr(event, "page", None)
        self.running_ids.add(routine_id)
        self.refresh()

        def worker() -> None:
            try:
                result = self.routine_service.execute_manual(routine_id)
            except Exception as error:
                result = {
                    "status": "error",
                    "message": str(error) or "Não foi possível executar a rotina.",
                }

            def finish() -> None:
                self.running_ids.discard(routine_id)
                self.refresh()
                status = str(result.get("status", "error"))
                message = str(result.get("message") or "Execução concluída.")
                if result.get("already_running"):
                    self._show("warning", message)
                elif status == "success":
                    self._show("success", message)
                elif status == "partial":
                    self._show("warning", message)
                else:
                    self._show("error", message)

            if page is not None:
                async def finish_async() -> None:
                    finish()

                page.run_task(finish_async)
            else:
                finish()

        if page is not None:
            page.run_thread(worker)
        else:
            worker()

    def confirm_delete(self, event: ft.ControlEvent, routine_id: int) -> None:
        page = getattr(event, "page", None)
        if page is None:
            return
        routine = next(
            (item for item in self.routines if item.get("id") == routine_id),
            None,
        )
        routine_name = str(routine.get("name")) if routine else "esta rotina"
        dialog: ft.AlertDialog

        def close_dialog(close_event: ft.ControlEvent) -> None:
            dialog.open = False
            close_event.page.update()

        def delete(delete_event: ft.ControlEvent) -> None:
            try:
                self.routine_service.delete_routine(routine_id)
            except Exception as error:
                self._show("error", str(error))
                return
            dialog.open = False
            delete_event.page.update()
            self.refresh()
            self._show("success", "Rotina excluída com sucesso.")

        dialog = custom_dialog(
            title="Excluir rotina",
            message=f"Deseja excluir a rotina '{routine_name}'? O histórico será preservado.",
            kind="warning",
            modal=True,
            actions=[
                build_secondary_button("Cancelar", close_dialog, height=40),
                build_primary_button("Excluir", delete, height=40),
            ],
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    def _open_form(
        self,
        event: ft.ControlEvent,
        routine_id: int | None,
    ) -> None:
        page = getattr(event, "page", None)
        if page is None:
            return
        try:
            routine = (
                self.routine_service.get_routine(routine_id)
                if routine_id is not None
                else None
            )
            modules = self.routine_service.list_executable_modules()
        except Exception as error:
            self._show("error", str(error))
            return
        form = RoutineFormState(
            parent=self,
            routine=routine,
            modules=modules,
        )
        dialog = form.build_dialog()
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    def _build_row(self, routine: dict[str, object]) -> dict[str, object]:
        routine_id = int(routine["id"])
        is_running = routine_id in self.running_ids
        schedule_valid = bool(routine.get("schedule_valid"))
        active_switch = ft.Switch(
            value=bool(routine.get("active")),
            disabled=is_running or not schedule_valid,
            tooltip=(
                "Corrija o agendamento antes de ativar."
                if not schedule_valid
                else "Ativar ou desativar rotina"
            ),
            on_change=lambda event, item_id=routine_id: self.on_toggle_active(
                event,
                item_id,
            ),
        )
        status_label = (
            "Agendamento inválido"
            if not schedule_valid
            else "Executando"
            if is_running
            else "Ativa"
            if routine.get("active")
            else "Inativa"
        )
        return {
            "name": ft.Text(
                str(routine.get("name") or "-"),
                size=13,
                color=TEXT_PRIMARY,
                weight=ft.FontWeight.W_600,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            "schedule": ft.Text(
                str(routine.get("schedule_description") or "-"),
                size=12,
                color=CANCEL if not schedule_valid else TEXT_PRIMARY,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
                tooltip=str(routine.get("schedule_description") or "-"),
            ),
            "modules": str(routine.get("module_count", 0)),
            "next_run": _format_datetime(routine.get("next_run_at")),
            "last_run": _format_datetime(routine.get("last_run_at")),
            "status": ft.Row(
                spacing=4,
                controls=[
                    active_switch,
                    ft.Text(status_label, size=11, color=TEXT_SECONDARY),
                ],
            ),
            "actions": ft.Row(
                spacing=0,
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.PLAY_ARROW_ROUNDED,
                        icon_color=PASTEL_DARK_PURPLE,
                        disabled=is_running,
                        width=36,
                        height=36,
                        tooltip="Executar agora",
                        on_click=lambda event, item_id=routine_id: self.execute_now(
                            event,
                            item_id,
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT_ROUNDED,
                        icon_color=PASTEL_DARK_PURPLE,
                        disabled=is_running,
                        width=36,
                        height=36,
                        tooltip="Editar",
                        on_click=lambda event, item_id=routine_id: self.open_edit_form(
                            event,
                            item_id,
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        icon_color=CANCEL,
                        disabled=is_running,
                        width=36,
                        height=36,
                        tooltip="Excluir",
                        on_click=lambda event, item_id=routine_id: self.confirm_delete(
                            event,
                            item_id,
                        ),
                    ),
                ],
            ),
        }

    def _build_error_state(self, error: Exception) -> ft.Container:
        return ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=CANCEL, size=32),
                    ft.Text(
                        "Não foi possível carregar as rotinas.",
                        color=TEXT_PRIMARY,
                        weight=ft.FontWeight.W_600,
                    ),
                    ft.Text(str(error), color=TEXT_SECONDARY, size=12),
                    build_secondary_button("Tentar novamente", lambda event: self.refresh()),
                ],
            ),
        )

    def _show(self, kind: str, message: str) -> None:
        if self.toaster_handler is None:
            return
        method = getattr(self.toaster_handler, f"show_{kind}", None)
        if callable(method):
            method(message)

    def _update_if_mounted(self, control: ft.Control) -> None:
        try:
            if control.page is not None:
                control.update()
        except RuntimeError:
            return


class RoutineFormState:
    def __init__(
        self,
        *,
        parent: RoutinesViewState,
        routine: dict[str, object] | None,
        modules: list[dict[str, object]],
    ) -> None:
        self.parent = parent
        self.routine = routine
        self.modules = modules
        self.modules_by_id = {
            int(module["module_id"]): module
            for module in modules
        }
        self.steps = [dict(action) for action in (routine or {}).get("actions", [])]
        self.dialog: ft.AlertDialog | None = None
        self.day_controls = ft.Column(spacing=8)
        self.day_dropdown: ft.Dropdown | None = None
        self.month_day_field: ft.TextField | None = None
        self.all_weekdays_checkbox: ft.Checkbox | None = None
        self.save_button: ft.FilledButton | None = None
        self.month_day_draft = ""
        self.steps_container = ft.Column(spacing=8)
        self.schedule_error = ft.Text(
            "",
            size=12,
            color=CANCEL,
            visible=False,
        )

        schedule_valid = bool((routine or {}).get("schedule_valid", True))
        self.name_field = build_text_field(
            "Nome da rotina",
            str((routine or {}).get("name") or ""),
        )
        self.name_field.on_change = self.on_form_value_change
        self.schedule_type_field = build_dropdown(
            "Tipo de repetição",
            str((routine or {}).get("schedule_type") or WEEKLY),
            (
                (WEEKLY, "Dias da semana"),
                (MONTHLY, "Dias do mês"),
            ),
            on_select=self.on_schedule_type_change,
        )
        self.time_field = build_text_field(
            "Horário",
            str((routine or {}).get("time") or "08:00"),
            helper="Use o formato HH:mm. Horário local.",
        )
        self.time_field.on_change = self.on_schedule_value_change
        self.active_switch = ft.Switch(
            label="Rotina ativa",
            value=(bool(routine.get("active")) if routine is not None else True),
        )
        self.stop_checkbox = ft.Checkbox(
            label="Parar se alguma requisição falhar",
            value=bool((routine or {}).get("stop_on_failure", True)),
        )
        available_modules = [
            module for module in modules if bool(module.get("is_available"))
        ]
        self.module_dropdown = build_dropdown(
            "Módulo",
            "",
            tuple(
                (str(module["module_id"]), str(module["path"]))
                for module in available_modules
            ),
            helper="Selecione um módulo executável e disponível.",
            menu_height=320,
        )
        self.saved_days = set((routine or {}).get("days", []))
        if not schedule_valid and routine is not None:
            self.schedule_error.value = str(
                routine.get("schedule_error")
                or "O agendamento precisa ser corrigido."
            )
            self.schedule_error.visible = True

    def build_dialog(self) -> ft.AlertDialog:
        create_mode = self.routine is None
        self.save_button = build_primary_button(
            "Criar rotina" if create_mode else "Salvar alterações",
            self.submit,
            disabled=True,
            height=40,
        )
        self._render_days()
        self._render_steps()
        self.dialog = custom_dialog(
            title="Nova rotina" if create_mode else "Editar rotina",
            icon=ft.Icons.AUTORENEW_ROUNDED,
            modal=True,
            alignment=ft.Alignment.CENTER,
            inset_padding=ft.Padding(left=36, top=24, right=36, bottom=24),
            content=ft.Container(
                width=890,
                height=620,
                content=ft.Tabs(
                    length=3,
                    expand=True,
                    content=ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            ft.TabBar(
                                indicator_color=PASTEL_DARK_PURPLE,
                                label_color=PASTEL_DARK_PURPLE,
                                unselected_label_color=TEXT_SECONDARY,
                                divider_color=BORDER,
                                tabs=[
                                    ft.Tab(label="Geral"),
                                    ft.Tab(label="Agendamento"),
                                    ft.Tab(label="Módulos"),
                                ],
                            ),
                            ft.TabBarView(
                                expand=True,
                                controls=[
                                    _build_form_tab(
                                        [
                                            self.name_field,
                                            _build_form_section(
                                                "Comportamento",
                                                "Defina quando a rotina fica disponível e como reage a falhas.",
                                                [
                                                    ft.Row(
                                                        spacing=28,
                                                        controls=[
                                                            self.active_switch,
                                                            self.stop_checkbox,
                                                        ],
                                                    )
                                                ],
                                            ),
                                        ]
                                    ),
                                    _build_form_tab(
                                        [
                                            _build_form_section(
                                                "Agendamento",
                                                "Escolha a repetição e o horário local da execução.",
                                                [
                                                    ft.Row(
                                                        spacing=12,
                                                        controls=[
                                                            self.schedule_type_field,
                                                            self.time_field,
                                                        ],
                                                    ),
                                                    self.day_controls,
                                                    self.schedule_error,
                                                ],
                                            )
                                        ]
                                    ),
                                    _build_form_tab(
                                        [
                                            _build_form_section(
                                                "Módulos da rotina",
                                                "Adicione e ordene as etapas que serão executadas.",
                                                [
                                                    ft.Row(
                                                        spacing=10,
                                                        controls=[
                                                            self.module_dropdown,
                                                            build_primary_button(
                                                                "Adicionar módulo",
                                                                self.add_module,
                                                                width=170,
                                                                height=42,
                                                            ),
                                                        ],
                                                    ),
                                                    self.steps_container,
                                                ],
                                            )
                                        ]
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
            ),
            actions=[
                build_secondary_button("Cancelar", self.cancel, height=40),
                self.save_button,
            ],
        )
        self._refresh_save_state()
        return self.dialog

    def on_schedule_type_change(self, event: ft.ControlEvent) -> None:
        self.saved_days = set()
        self.month_day_draft = ""
        self._render_days()
        self.parent._update_if_mounted(self.day_controls)
        self.on_schedule_value_change(event)

    def on_form_value_change(self, event: ft.ControlEvent) -> None:
        del event
        name = str(self.name_field.value or "").strip()
        self.name_field.error = (
            "O nome aceita até 100 caracteres."
            if len(name) > 100
            else None
        )
        self.parent._update_if_mounted(self.name_field)
        self._refresh_save_state()

    def on_schedule_value_change(self, event: ft.ControlEvent) -> None:
        del event
        try:
            self.parent.routine_service.schedule_service.build_cron(
                str(self.schedule_type_field.value),
                self._selected_days(),
                str(self.time_field.value or ""),
            )
            self.schedule_error.visible = False
        except ValueError as error:
            self.schedule_error.value = str(error)
            self.schedule_error.visible = True
        self.parent._update_if_mounted(self.schedule_error)
        self._refresh_save_state()

    def on_all_weekdays_change(self, event: ft.ControlEvent) -> None:
        self.saved_days = set(WEEKDAY_KEYS) if bool(event.control.value) else set()
        self._render_days()
        self.on_schedule_value_change(event)
        self.parent._update_if_mounted(self.day_controls)

    def on_day_selected(self, event: ft.ControlEvent) -> None:
        raw_value = event.control.value
        if raw_value in (None, ""):
            return
        value: str | int = str(raw_value)
        if self.schedule_type_field.value == MONTHLY:
            value = int(value)
        self.saved_days.add(value)
        self._render_days()
        self.on_schedule_value_change(event)
        self.parent._update_if_mounted(self.day_controls)

    def on_month_day_change(self, event: ft.ControlEvent) -> None:
        self.month_day_draft = str(event.control.value or "").strip()
        self._apply_month_day_feedback()
        self._refresh_save_state()

    def add_month_day(self, event: ft.ControlEvent) -> None:
        error = self._month_day_error(self.month_day_draft)
        if error:
            if self.month_day_field is not None:
                self.month_day_field.error = error
                self.parent._update_if_mounted(self.month_day_field)
            return

        day = int(self.month_day_draft)
        if day in self.saved_days:
            if self.month_day_field is not None:
                self.month_day_field.error = "Este dia já foi adicionado."
                self.parent._update_if_mounted(self.month_day_field)
            return
        if len(self.saved_days) >= 31:
            if self.month_day_field is not None:
                self.month_day_field.error = "O limite de 31 dias foi atingido."
                self.parent._update_if_mounted(self.month_day_field)
            return

        self.saved_days.add(day)
        self.month_day_draft = ""
        self._render_days()
        self.on_schedule_value_change(event)
        self.parent._update_if_mounted(self.day_controls)

    def remove_day(self, event: ft.ControlEvent, day: str | int) -> None:
        self.saved_days.discard(day)
        self._render_days()
        self.on_schedule_value_change(event)
        self.parent._update_if_mounted(self.day_controls)

    def add_module(self, event: ft.ControlEvent) -> None:
        raw_module_id = self.module_dropdown.value
        if not raw_module_id or not str(raw_module_id).isdigit():
            self.parent._show("warning", "Selecione um módulo para adicionar.")
            return
        module_id = int(str(raw_module_id))
        module = self.modules_by_id.get(module_id)
        if module is None or not bool(module.get("is_available")):
            self.parent._show("error", "O módulo selecionado está indisponível.")
            return
        self.steps.append(
            {
                "action_id": None,
                "module_id": module_id,
                "active": True,
                "argument": None,
                "module_path": module["path"],
                "module_available": True,
                "module_error": "",
                "accepts_argument": bool(module.get("accepts_argument")),
                "requires_argument": bool(module.get("requires_argument")),
            }
        )
        self.module_dropdown.value = ""
        self._render_steps()
        self.parent._update_if_mounted(self.module_dropdown)
        self.parent._update_if_mounted(self.steps_container)
        self._refresh_save_state()

    def move_step(self, event: ft.ControlEvent, index: int, offset: int) -> None:
        del event
        target = index + offset
        if target < 0 or target >= len(self.steps):
            return
        self.steps[index], self.steps[target] = self.steps[target], self.steps[index]
        self._render_steps()
        self.parent._update_if_mounted(self.steps_container)
        self._refresh_save_state()

    def remove_step(self, event: ft.ControlEvent, index: int) -> None:
        del event
        self.steps.pop(index)
        self._render_steps()
        self.parent._update_if_mounted(self.steps_container)
        self._refresh_save_state()

    def cancel(self, event: ft.ControlEvent) -> None:
        if self.dialog is None:
            return
        self.dialog.open = False
        event.page.update()

    def submit(self, event: ft.ControlEvent) -> None:
        values = {
            "name": self.name_field.value or "",
            "schedule_type": self.schedule_type_field.value or "",
            "days": self._selected_days(),
            "time_value": self.time_field.value or "",
            "active": bool(self.active_switch.value),
            "stop_on_failure": bool(self.stop_checkbox.value),
            "actions": [
                {
                    "action_id": step.get("action_id"),
                    "module_id": step.get("module_id"),
                    "active": bool(step.get("active", True)),
                    "argument": step.get("argument"),
                }
                for step in self.steps
            ],
        }
        try:
            if self.routine is None:
                self.parent.routine_service.create_routine(**values)
                success_message = "Rotina criada com sucesso."
            else:
                self.parent.routine_service.update_routine(
                    int(self.routine["id"]),
                    **values,
                )
                success_message = "Rotina atualizada com sucesso."
        except Exception as error:
            self.parent._show("error", str(error))
            return
        if self.dialog is not None:
            self.dialog.open = False
            event.page.update()
        self.parent.refresh()
        self.parent._show("success", success_message)

    def _render_days(self) -> None:
        schedule_type = self.schedule_type_field.value or WEEKLY
        if schedule_type == WEEKLY:
            available_options = tuple(
                (key, WEEKDAY_LABELS[key].capitalize())
                for key in WEEKDAY_KEYS
                if key not in self.saved_days
            )
            selected_days = [
                key for key in WEEKDAY_KEYS if key in self.saved_days
            ]
            dropdown_label = "Adicionar dia da semana"
            self.day_dropdown = build_dropdown(
                dropdown_label,
                "",
                available_options,
                helper="Selecione quantos dias desejar.",
                menu_height=260,
                width=340,
                expand=False,
                on_select=self.on_day_selected,
            )
            self.month_day_field = None
            self.all_weekdays_checkbox = ft.Checkbox(
                label=ft.Text("Todos os dias", no_wrap=True),
                value=len(selected_days) == len(WEEKDAY_KEYS),
                active_color=PASTEL_DARK_PURPLE,
                on_change=self.on_all_weekdays_change,
            )
            selector_controls: list[ft.Control] = [
                self.day_dropdown,
                self.all_weekdays_checkbox,
            ]
        else:
            selected_days = sorted(
                int(day) for day in self.saved_days
            )
            self.day_dropdown = None
            self.all_weekdays_checkbox = None
            self.month_day_field = build_text_field(
                "Dia do mês",
                self.month_day_draft,
                helper=self._month_day_helper(),
                expand=False,
            )
            self.month_day_field.width = 210
            self.month_day_field.keyboard_type = ft.KeyboardType.NUMBER
            self.month_day_field.input_filter = ft.NumbersOnlyInputFilter()
            self.month_day_field.on_change = self.on_month_day_change
            self.month_day_field.on_submit = self.add_month_day
            self.month_day_field.error = self._month_day_error(
                self.month_day_draft,
                allow_empty=True,
            )
            add_day_button = ft.IconButton(
                icon=ft.Icons.ADD_ROUNDED,
                icon_color=ft.Colors.WHITE,
                bgcolor=PASTEL_DARK_PURPLE,
                width=42,
                height=42,
                disabled=len(selected_days) >= 31,
                tooltip="Adicionar dia do mês",
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=5),
                ),
                on_click=self.add_month_day,
            )
            selector_controls = [self.month_day_field, add_day_button]

        chips = [
            self._build_day_chip(day, schedule_type)
            for day in selected_days
        ]
        selected_content: ft.Control
        if chips:
            selected_content = ft.Row(
                wrap=True,
                spacing=7,
                run_spacing=7,
                controls=chips,
            )
        else:
            selected_content = ft.Text(
                "Nenhum dia selecionado.",
                size=12,
                color=TEXT_SECONDARY,
            )
        self.day_controls.controls = [
            ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=selector_controls,
            ),
            ft.Container(
                padding=10,
                bgcolor=SURFACE,
                border=ft.Border.all(1, BORDER),
                border_radius=8,
                content=selected_content,
            ),
        ]

    def _month_day_error(
        self,
        raw_value: str,
        *,
        allow_empty: bool = False,
    ) -> str | None:
        value = str(raw_value or "").strip()
        if not value:
            return None if allow_empty else "Informe um dia do mês."
        if not value.isdigit():
            return "O dia precisa ser um número inteiro."
        day = int(value)
        if day < 1:
            return "O dia precisa ser maior que zero."
        if day > 31:
            return "O dia não pode ser maior que 31."
        return None

    def _month_day_helper(self) -> str:
        if not self._month_day_error(self.month_day_draft, allow_empty=True):
            if self.month_day_draft and int(self.month_day_draft) > 28:
                return "Este dia pode não existir em todos os meses."
        return "Informe um número inteiro entre 1 e 31."

    def _apply_month_day_feedback(self) -> None:
        if self.month_day_field is None:
            return
        self.month_day_field.error = self._month_day_error(
            self.month_day_draft,
            allow_empty=True,
        )
        self.month_day_field.helper = self._month_day_helper()
        self.parent._update_if_mounted(self.month_day_field)

    def _selected_days(self) -> list[str | int]:
        if self.schedule_type_field.value == MONTHLY:
            return sorted(int(day) for day in self.saved_days)
        return [key for key in WEEKDAY_KEYS if key in self.saved_days]

    def _build_day_chip(
        self,
        day: str | int,
        schedule_type: str,
    ) -> ft.Container:
        label = (
            WEEKDAY_LABELS[str(day)].capitalize()
            if schedule_type == WEEKLY
            else f"Dia {day}"
        )
        return ft.Container(
            height=30,
            padding=ft.Padding(left=10, top=0, right=3, bottom=0),
            bgcolor=PASTEL_BLUE,
            border=ft.Border.all(1, BORDER),
            border_radius=15,
            content=ft.Row(
                tight=True,
                spacing=2,
                controls=[
                    ft.Text(label, size=12, color=TEXT_PRIMARY),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_size=14,
                        icon_color=TEXT_SECONDARY,
                        width=26,
                        height=26,
                        tooltip=f"Remover {label.lower()}",
                        on_click=lambda event, selected_day=day: self.remove_day(
                            event,
                            selected_day,
                        ),
                    ),
                ],
            ),
        )

    def _render_steps(self) -> None:
        if not self.steps:
            self.steps_container.controls = [
                ft.Container(
                    padding=16,
                    alignment=ft.Alignment.CENTER,
                    border_radius=8,
                    content=ft.Text(
                        "Adicione ao menos um módulo.",
                        size=13,
                        color=TEXT_SECONDARY,
                    ),
                )
            ]
            return
        self.steps_container.controls = [
            self._build_step(step, index)
            for index, step in enumerate(self.steps)
        ]

    def _build_step(self, step: dict[str, object], index: int) -> ft.Container:
        available = bool(step.get("module_available"))
        header_controls: list[ft.Control] = [
            ft.Text(
                f"{index + 1}. {step.get('module_path') or 'Módulo'}",
                expand=True,
                size=13,
                color=TEXT_PRIMARY,
                weight=ft.FontWeight.W_600,
            )
        ]
        if not available:
            header_controls.append(
                ft.Container(
                    padding=ft.Padding(left=8, top=3, right=8, bottom=3),
                    bgcolor=WARNING,
                    border_radius=8,
                    content=ft.Text("Indisponível", size=11, color=TEXT_PRIMARY),
                )
            )
        header_controls.extend(
            [
                ft.IconButton(
                    icon=ft.Icons.ARROW_UPWARD_ROUNDED,
                    icon_size=18,
                    width=34,
                    height=34,
                    disabled=index == 0,
                    tooltip="Subir etapa",
                    on_click=lambda event, item_index=index: self.move_step(
                        event,
                        item_index,
                        -1,
                    ),
                ),
                ft.IconButton(
                    icon=ft.Icons.ARROW_DOWNWARD_ROUNDED,
                    icon_size=18,
                    width=34,
                    height=34,
                    disabled=index == len(self.steps) - 1,
                    tooltip="Descer etapa",
                    on_click=lambda event, item_index=index: self.move_step(
                        event,
                        item_index,
                        1,
                    ),
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_size=18,
                    icon_color=CANCEL,
                    width=34,
                    height=34,
                    tooltip="Remover etapa",
                    on_click=lambda event, item_index=index: self.remove_step(
                        event,
                        item_index,
                    ),
                ),
            ]
        )
        controls: list[ft.Control] = [ft.Row(spacing=4, controls=header_controls)]
        if not available:
            controls.append(
                ft.Text(
                    str(step.get("module_error") or "Esta etapa não pode ser executada."),
                    size=12,
                    color=CANCEL,
                )
            )
        if bool(step.get("accepts_argument")):
            argument_field = build_text_field(
                "Argumento da etapa",
                str(step.get("argument") or ""),
                helper=(
                    "Obrigatório para este módulo."
                    if step.get("requires_argument")
                    else "Valor fixo usado somente por esta rotina."
                ),
            )

            def update_argument(
                event: ft.ControlEvent,
                item: dict[str, object] = step,
            ) -> None:
                item["argument"] = event.control.value or None
                self._refresh_save_state()

            argument_field.on_change = update_argument
            controls.append(argument_field)
        return ft.Container(
            padding=12,
            bgcolor=SURFACE if available else BLUE_GREY,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            content=ft.Column(spacing=8, controls=controls),
        )

    def _is_form_valid(self) -> bool:
        name = str(self.name_field.value or "").strip()
        if not name or len(name) > 100 or not self.steps:
            return False
        try:
            self.parent.routine_service.schedule_service.build_cron(
                str(self.schedule_type_field.value or ""),
                self._selected_days(),
                str(self.time_field.value or ""),
            )
        except ValueError:
            return False
        for step in self.steps:
            if type(step.get("module_id")) is not int:
                return False
            if not bool(step.get("module_available")):
                return False
            if step.get("requires_argument") and not str(
                step.get("argument") or ""
            ).strip():
                return False
        return True

    def _refresh_save_state(self) -> None:
        if self.save_button is None:
            return
        self.save_button.disabled = not self._is_form_valid()
        self.parent._update_if_mounted(self.save_button)
def _format_datetime(value: object) -> str:
    if not isinstance(value, datetime):
        return "-"
    if value.tzinfo is not None:
        value = value.astimezone()
    return value.strftime("%d/%m/%Y %H:%M")


def _build_form_tab(controls: list[ft.Control]) -> ft.Container:
    return ft.Container(
        padding=ft.Padding(left=2, top=18, right=2, bottom=8),
        content=ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=18,
            controls=controls,
        ),
    )


def _build_form_section(
    title: str,
    subtitle: str,
    controls: list[ft.Control],
) -> ft.Column:
    return ft.Column(
        spacing=8,
        controls=[
            ft.Column(
                spacing=1,
                controls=[
                    ft.Text(
                        title,
                        size=15,
                        color=TEXT_PRIMARY,
                        weight=ft.FontWeight.W_700,
                    ),
                    ft.Text(subtitle, size=12, color=TEXT_SECONDARY),
                ],
            ),
            ft.Container(
                padding=14,
                bgcolor=BLUE_GREY,
                border=ft.Border.all(1, BORDER),
                border_radius=8,
                content=ft.Column(spacing=12, controls=controls),
            ),
        ],
    )
