from __future__ import annotations

import flet as ft

from database.db import SessionLocal
from services.home_service import HomeService
from services.module_service import get_module_detail
from ui.modules.components.not_found import build_module_not_found_view
from ui.modules.components.status_chip import build_status_chip
from ui.modules.constants import ERROR_TAB, MODULE_TABS
from ui.modules.execution import ModuleExecutionMixin
from ui.modules.views.about_tab import ModuleAboutTabMixin
from ui.modules.views.error_tab import ModuleErrorTabMixin
from ui.modules.views.execution_tab import ModuleExecutionTabMixin
from ui.modules.views.logs_tab import ModuleLogsTabMixin
from ui.modules.views.settings_tab import ModuleSettingsTabMixin
from ui.shared.components.form_controls import (
    FloatingSaveBar,
    build_primary_button,
    build_text_field,
)
from ui.shared.components.material_icons import material_icon
from ui.shared.components.route_content_container import build_route_content_container
from ui.shared.components.toaster_handler import ToasterHandler
from ui.theme.colors import (
    BORDER,
    PASTEL_DARK_PURPLE,
    PASTEL_PURPLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


def build_module_view(
    module_id: int,
    toaster_handler: ToasterHandler | None = None,
    session_factory=SessionLocal,
) -> ft.Container:
    detail = get_module_detail(module_id, session_factory)
    if detail is None:
        return build_module_not_found_view()
    return ModuleViewState(
        detail,
        toaster_handler,
        session_factory,
    ).build()


class ModuleViewState(
    ModuleExecutionMixin,
    ModuleExecutionTabMixin,
    ModuleAboutTabMixin,
    ModuleSettingsTabMixin,
    ModuleLogsTabMixin,
    ModuleErrorTabMixin,
):
    def __init__(
        self,
        detail: dict[str, object],
        toaster_handler: ToasterHandler | None,
        session_factory,
    ) -> None:
        self.detail = detail
        self.toaster_handler = toaster_handler
        self.session_factory = session_factory
        self.home_service = HomeService(session_factory)
        self.technical_errors = list(detail["technical_errors"])
        self.active_tab = "error" if self.technical_errors else "about"
        self.tab_definitions = self._build_tab_definitions()
        self.tab_content = ft.Container(expand=True)
        self.tab_buttons: dict[str, ft.Container] = {}
        self.tab_views: dict[str, ft.Control] = {}
        self.variable_fields: dict[str, ft.TextField] = {}
        self.model_value_controls: dict[str, ft.Control] = {}
        self.settings_save_bar: FloatingSaveBar | None = None
        self.execution_save_bar: FloatingSaveBar | None = None
        self.module_state_saved: dict[str, str] = {}
        self.module_state_edited: dict[str, str] | None = None
        self.execution_state_saved: dict[str, object] = {}
        self.execution_state_edited: dict[str, object] | None = None
        self.is_executing = False
        self.http_request = detail.get("http_request")

        self.custom_call_name_field = build_text_field(
            "Nome de chamada personalizado",
            str(detail["custom_call_name"]),
            helper="Opcional. Substitui o nome personalizado anterior.",
            disabled=not bool(detail["is_available"]),
        )
        http_argument_enabled = bool(
            self.http_request
            and self.http_request.get("argument_enabled")
        )
        accepts_argument = (
            http_argument_enabled
            if self.http_request is not None
            else bool(detail["has_arguments"])
        )
        self.argument_explanation = (
            "Este módulo não utiliza argumento de execução."
            if self.http_request is not None and not http_argument_enabled
            else (
                "Informe a string que substituirá {{argument}} na requisição."
                if self.http_request is not None
                else (
                    "Informe o argumento que será enviado ao módulo ao executar."
                    if accepts_argument
                    else "Este módulo não utiliza argumento de execução."
                )
            )
        )
        self.argument_field = (
            build_text_field(
                "Argumento da execução",
                str(self.http_request.get("argument") or "")
                if self.http_request is not None
                else "",
                helper=self.argument_explanation,
                disabled=(
                    not bool(detail["is_available"])
                    or not accepts_argument
                ),
            )
            if bool(detail["is_executable"])
            else None
        )
        self.execute_button = build_primary_button(
            "Executar",
            self.on_execute,
            disabled=not (
                bool(detail["is_available"])
                and bool(detail["is_executable"])
            ),
            visible=(
                bool(detail["is_executable"])
            ),
        )
        self.execute_button.height = 40
        self.execution_result_card = self._build_execution_result_card()
        self.log_container = ft.Container(expand=True)

    def build(self) -> ft.Container:
        for key, label, icon in self.tab_definitions:
            self.tab_buttons[key] = self._build_tab_button(key, label, icon)

        self.tab_views = {
            "about": self._build_about_tab(),
            "settings": self._build_settings_tab(),
        }
        if bool(self.detail["is_executable"]):
            self.tab_views["execution"] = self._build_execution_tab()
            self.tab_views["logs"] = self._build_log_tab()
        if self.technical_errors:
            self.tab_views["error"] = self._build_error_tab()
        self._render_tab()

        return build_route_content_container(
            icon=material_icon(
                str(self.detail["icon"]),
                size=25,
                color=PASTEL_DARK_PURPLE,
            ),
            title=str(self.detail["name"]),
            subtitle=self._build_breadcrumb(),
            trailing=self._build_header_trailing(),
            content=ft.Column(
                expand=True,
                spacing=16,
                controls=[
                    self.execution_result_card,
                    ft.Container(
                        border=ft.Border.only(bottom=ft.BorderSide(1, BORDER)),
                        content=ft.Row(
                            spacing=20,
                            controls=list(self.tab_buttons.values()),
                        ),
                    ),
                    self.tab_content,
                ],
            ),
        )

    def _build_tab_definitions(self) -> tuple[tuple[str, str, object], ...]:
        module_tabs = tuple(
            tab for tab in MODULE_TABS
            if tab[0] not in {"execution", "logs"}
            or bool(self.detail["is_executable"])
        )
        if self.technical_errors:
            return (ERROR_TAB, *module_tabs)
        return module_tabs

    def _build_header_trailing(self) -> ft.Row:
        controls: list[ft.Control] = []
        if self.http_request is None:
            controls.append(self.execute_button)
        controls.append(build_status_chip(str(self.detail["status"])))
        return ft.Row(
            tight=True,
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=controls,
        )

    def _build_breadcrumb(self) -> ft.Row:
        controls: list[ft.Control] = []
        breadcrumb = list(self.detail["breadcrumb"])
        for index, item in enumerate(breadcrumb):
            if index:
                controls.append(
                    ft.Icon(
                        ft.Icons.CHEVRON_RIGHT_ROUNDED,
                        size=15,
                        color=TEXT_SECONDARY,
                    )
                )
            controls.append(
                ft.Text(
                    str(item["name"]),
                    size=12,
                    color=TEXT_SECONDARY,
                )
            )
        return ft.Row(tight=True, spacing=3, controls=controls)

    def _build_tab_button(self, key: str, label: str, icon) -> ft.Container:
        is_active = key == self.active_tab
        icon_control = ft.Icon(
            icon,
            size=18,
            color=TEXT_PRIMARY if is_active else TEXT_SECONDARY,
        )
        text_control = ft.Text(
            label,
            size=14,
            weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_500,
            color=TEXT_PRIMARY if is_active else TEXT_SECONDARY,
        )
        indicator = ft.Container(
            height=50,
            padding=ft.Padding(left=4, top=0, right=4, bottom=12),
            alignment=ft.Alignment.BOTTOM_CENTER,
            border=ft.Border.only(
                bottom=ft.BorderSide(
                    width=3 if is_active else 0,
                    color=PASTEL_PURPLE if is_active else ft.Colors.TRANSPARENT,
                ),
            ),
            content=ft.Row(
                tight=True,
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[icon_control, text_control],
            ),
        )

        def on_hover(event: ft.ControlEvent) -> None:
            hovering = str(event.data).lower() == "true"
            if key != self.active_tab:
                color = TEXT_PRIMARY if hovering else TEXT_SECONDARY
                icon_control.color = color
                text_control.color = color
            event.control.bgcolor = (
                ft.Colors.with_opacity(0.04, PASTEL_PURPLE)
                if hovering
                else ft.Colors.TRANSPARENT
            )
            event.control.update()

        return ft.Container(
            height=50,
            padding=ft.Padding(left=12, top=0, right=12, bottom=0),
            alignment=ft.Alignment.BOTTOM_CENTER,
            bgcolor=ft.Colors.TRANSPARENT,
            on_click=lambda _, selected=key: self.on_select_tab(selected),
            on_hover=on_hover,
            ink=True,
            ink_color=ft.Colors.with_opacity(0.08, PASTEL_PURPLE),
            content=indicator,
        )

    def on_select_tab(self, key: str) -> None:
        if key not in self.tab_views:
            return
        self.active_tab = key
        if key == "logs":
            self._refresh_logs()
        self._render_tab()
        self._update_if_mounted(self.tab_content)
        for button in self.tab_buttons.values():
            self._update_if_mounted(button)

    def _render_tab(self) -> None:
        self._sync_tab_buttons()
        self.tab_content.content = self.tab_views[self.active_tab]

    def _sync_tab_buttons(self) -> None:
        for key, button in self.tab_buttons.items():
            is_active = key == self.active_tab
            indicator = button.content
            tab_row = indicator.content
            icon_control, text_control = tab_row.controls
            indicator.border = ft.Border.only(
                bottom=ft.BorderSide(
                    width=3 if is_active else 0,
                    color=PASTEL_PURPLE if is_active else ft.Colors.TRANSPARENT,
                ),
            )
            icon_control.color = TEXT_PRIMARY if is_active else TEXT_SECONDARY
            text_control.color = TEXT_PRIMARY if is_active else TEXT_SECONDARY
            text_control.weight = (
                ft.FontWeight.W_600 if is_active else ft.FontWeight.W_500
            )
