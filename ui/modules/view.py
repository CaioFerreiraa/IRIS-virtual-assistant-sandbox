from __future__ import annotations

import flet as ft

from database.db import SessionLocal
from services.home_service import HomeService
from services.module_service import (
    get_module_detail,
    save_auto_start_preference,
    save_module_settings,
)
from ui.history.view import HISTORY_COLUMNS, load_history_rows
from ui.shared.components.form_controls import build_primary_button, build_text_field
from ui.shared.components.material_icons import material_icon
from ui.shared.components.route_content_container import build_route_content_container
from ui.shared.components.table import build_responsive_table
from ui.shared.components.toaster_handler import ToasterHandler
from ui.theme.colors import (
    BLUE_GREY,
    BORDER,
    CANCEL,
    CONFIRM,
    GREY_100,
    PASTEL_BLUE,
    PASTEL_DARK_PURPLE,
    PASTEL_PURPLE,
    SURFACE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)


MODULE_TABS = (
    ("about", "Sobre", ft.Icons.INFO_OUTLINE_ROUNDED),
    ("settings", "Configurações", ft.Icons.TUNE_ROUNDED),
    ("logs", "Log", ft.Icons.HISTORY_ROUNDED),
)
ERROR_TAB = ("error", "Erro", ft.Icons.ERROR_OUTLINE_ROUNDED)


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


def build_module_not_found_view() -> ft.Container:
    return build_route_content_container(
        icon=ft.Icons.SEARCH_OFF_ROUNDED,
        title="Módulo não encontrado",
        subtitle="O identificador informado não corresponde a um módulo registrado.",
        content=ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    ft.Icon(
                        ft.Icons.ROUTE_ROUNDED,
                        size=44,
                        color=PASTEL_DARK_PURPLE,
                    ),
                    ft.Text(
                        "Selecione outro módulo na barra lateral.",
                        size=15,
                        color=TEXT_PRIMARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
            ),
        ),
    )


class ModuleViewState:
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
        self.tab_definitions = (
            (ERROR_TAB, *MODULE_TABS)
            if self.technical_errors
            else MODULE_TABS
        )
        self.tab_content = ft.Container(expand=True)
        self.tab_buttons: dict[str, ft.Container] = {}
        self.tab_views: dict[str, ft.Control] = {}
        self.variable_fields: dict[str, ft.TextField] = {}
        self.model_value_controls: dict[str, ft.Text] = {}
        self.is_executing = False

        self.custom_call_name_field = build_text_field(
            "Nome de chamada personalizado",
            str(detail["custom_call_name"]),
            helper="Opcional. Substitui o nome personalizado anterior.",
            disabled=not bool(detail["is_available"]),
        )
        self.argument_field = (
            build_text_field(
                "Argumento da execução",
                "",
                helper="Informe o argumento que será enviado ao módulo ao executar.",
                disabled=not bool(detail["is_available"]),
            )
            if bool(detail["has_arguments"])
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
                bool(detail["is_available"])
                and bool(detail["is_executable"])
            ),
        )
        self.log_container = ft.Container(expand=True)

    def build(self) -> ft.Container:
        for key, label, icon in self.tab_definitions:
            self.tab_buttons[key] = self._build_tab_button(key, label, icon)

        self.tab_views = {
            "about": self._build_about_tab(),
            "settings": self._build_settings_tab(),
            "logs": self._build_log_tab(),
        }
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

    def _build_header_trailing(self) -> ft.Row:
        return ft.Row(
            tight=True,
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                self.execute_button,
                _build_status_chip(str(self.detail["status"])),
            ],
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

    def _build_about_tab(self) -> ft.Column:
        controls: list[ft.Control] = [
            _build_card(
                "Descrição",
                ft.Text(
                    str(self.detail["description"])
                    or "Este módulo não possui descrição.",
                    size=14,
                    color=TEXT_PRIMARY,
                    selectable=True,
                ),
            )
        ]
        readme_content = str(self.detail["readme_content"])
        if readme_content:
            controls.append(
                _build_card(
                    "README",
                    ft.Markdown(
                        readme_content,
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        code_theme=ft.MarkdownCodeTheme.A11Y_LIGHT,
                        auto_follow_links=False,
                    ),
                )
            )

        manifest_content = str(self.detail["manifest_content"])
        if manifest_content:
            controls.append(
                _build_card(
                    "module.json",
                    ft.Container(
                        bgcolor=GREY_100,
                        border=ft.Border.all(1, BORDER),
                        border_radius=8,
                        padding=16,
                        content=ft.Text(
                            manifest_content,
                            size=12,
                            color=TEXT_PRIMARY,
                            font_family="Consolas",
                            selectable=True,
                        ),
                    ),
                )
            )
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=16,
            controls=controls,
        )

    def _build_settings_tab(self) -> ft.Column:
        controls: list[ft.Control] = [
            _build_card(
                "Dados do módulo",
                ft.ResponsiveRow(
                    spacing=12,
                    run_spacing=12,
                    controls=[
                        self._build_model_value(label, value)
                        for label, value in list(self.detail["model_data"])
                    ],
                ),
            ),
            self._build_preferences_card(),
        ]

        editable_variables = [
            variable
            for variable in list(self.detail["variables"])
            if bool(variable["user_editable"])
        ]
        if editable_variables:
            fields: list[ft.Control] = []
            for variable in editable_variables:
                label = str(variable["label"])
                if bool(variable["required"]):
                    label = f"{label} *"
                field = build_text_field(
                    label,
                    str(variable["value"]),
                    helper=str(variable["description"]),
                    disabled=not bool(self.detail["is_available"]),
                )
                self.variable_fields[str(variable["key"])] = field
                fields.append(field)
            controls.append(
                _build_card(
                    "Variáveis da requisição",
                    ft.Column(spacing=14, controls=fields),
                )
            )

        if self.argument_field is not None:
            controls.append(
                _build_card(
                    "Argumento",
                    ft.Column(
                        spacing=8,
                        controls=[
                            self.argument_field,
                            ft.Text(
                                "Este valor é usado somente na próxima execução e não é salvo.",
                                size=12,
                                color=TEXT_SECONDARY,
                            ),
                        ],
                    ),
                )
            )

        if bool(self.detail["is_available"]):
            controls.append(
                ft.Row(
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        build_primary_button(
                            "Salvar configurações",
                            self.on_save_settings,
                        )
                    ],
                )
            )
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=16,
            controls=controls,
        )

    def _build_model_value(self, label: str, value: str) -> ft.Container:
        value_control = ft.Text(
            value,
            size=13,
            color=TEXT_PRIMARY,
            selectable=True,
            max_lines=3,
            overflow=ft.TextOverflow.ELLIPSIS,
            tooltip=value,
        )
        self.model_value_controls[label] = value_control
        return ft.Container(
            col={"sm": 12, "md": 6, "lg": 4},
            padding=12,
            bgcolor=BLUE_GREY,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            content=ft.Column(
                tight=True,
                spacing=4,
                controls=[
                    ft.Text(
                        label,
                        size=11,
                        weight=ft.FontWeight.W_700,
                        color=TEXT_SECONDARY,
                    ),
                    value_control,
                ],
            ),
        )

    def _build_preferences_card(self) -> ft.Container:
        controls: list[ft.Control] = [self.custom_call_name_field]
        if bool(self.detail["is_available"]):
            can_auto_start = bool(self.detail["can_auto_start"])
            if can_auto_start:
                explanation = "A alteração será aplicada na próxima abertura da IRIS."
            elif bool(self.detail["supports_auto_start"]):
                explanation = (
                    "A inicialização automática está disponível somente para módulos raiz."
                )
            else:
                explanation = (
                    "O desenvolvedor deste módulo não declarou suporte à inicialização automática."
                )
            controls.append(
                ft.Container(
                    padding=14,
                    bgcolor=BLUE_GREY,
                    border=ft.Border.all(1, BORDER),
                    border_radius=8,
                    content=ft.Row(
                        spacing=14,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(
                                expand=True,
                                tight=True,
                                spacing=3,
                                controls=[
                                    ft.Text(
                                        "Iniciar com a IRIS",
                                        size=14,
                                        weight=ft.FontWeight.W_700,
                                        color=TEXT_PRIMARY,
                                    ),
                                    ft.Text(
                                        explanation,
                                        size=12,
                                        color=TEXT_SECONDARY,
                                    ),
                                ],
                            ),
                            ft.Switch(
                                value=bool(self.detail["auto_start_enabled"]),
                                disabled=not can_auto_start,
                                active_color=PASTEL_DARK_PURPLE,
                                active_track_color=PASTEL_PURPLE,
                                on_change=self.on_auto_start_change,
                            ),
                        ],
                    ),
                )
            )
        return _build_card(
            "Preferências",
            ft.Column(spacing=14, controls=controls),
        )

    def _build_log_tab(self) -> ft.Container:
        self._refresh_logs()
        return self.log_container

    def _refresh_logs(self) -> None:
        rows = load_history_rows(
            module_id=int(self.detail["id"]),
            session_factory=self.session_factory,
        )
        self.log_container.content = build_responsive_table(
            columns=HISTORY_COLUMNS,
            rows=rows,
            empty_message="Este módulo ainda não possui registros de execução.",
        )
        self._update_if_mounted(self.log_container)

    def _build_error_tab(self) -> ft.Column:
        cards: list[ft.Control] = []
        for error in self.technical_errors:
            is_submodule = bool(error.get("is_submodule"))
            module_name = str(error.get("module_name") or "Módulo")
            title = (
                f"Problema no submódulo {module_name}"
                if is_submodule
                else f"Problema no módulo {module_name}"
            )
            details: list[ft.Control] = [
                ft.Text(
                    str(error.get("message") or "O módulo apresentou um problema técnico."),
                    size=13,
                    color=TEXT_PRIMARY,
                    selectable=True,
                )
            ]
            log_path = str(error.get("log_path") or "")
            if log_path:
                details.extend(
                    [
                        ft.Text(
                            "Log técnico",
                            size=11,
                            weight=ft.FontWeight.W_700,
                            color=TEXT_SECONDARY,
                        ),
                        ft.Text(
                            log_path,
                            size=12,
                            color=TEXT_PRIMARY,
                            font_family="Consolas",
                            selectable=True,
                        ),
                    ]
                )
            cards.append(
                ft.Container(
                    padding=16,
                    bgcolor=ft.Colors.with_opacity(0.35, CANCEL),
                    border=ft.Border.all(1, CANCEL),
                    border_radius=8,
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Icon(
                                        ft.Icons.ERROR_OUTLINE_ROUNDED,
                                        size=20,
                                        color=PASTEL_DARK_PURPLE,
                                    ),
                                    ft.Text(
                                        title,
                                        size=15,
                                        weight=ft.FontWeight.W_700,
                                        color=TEXT_PRIMARY,
                                    ),
                                ],
                            ),
                            *details,
                        ],
                    ),
                )
            )
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=cards,
        )

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
            self._show_error(str(error) or "Não foi possível executar o módulo.")
        elif result is not None and result.get("success", True):
            self._show_success(
                self._result_message(result) or "Módulo executado com sucesso."
            )
        else:
            self._show_error(
                self._result_message(result or {}) or "O módulo retornou erro."
            )
        self._set_execute_loading(False)
        self._refresh_logs()

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


def _build_card(title: str, content: ft.Control) -> ft.Container:
    return ft.Container(
        padding=ft.Padding(left=18, top=16, right=18, bottom=18),
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=8,
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Text(
                    title,
                    size=17,
                    weight=ft.FontWeight.BOLD,
                    color=TEXT_PRIMARY,
                ),
                content,
            ],
        ),
    )


def _build_status_chip(status: str) -> ft.Container:
    color = {
        "disponível": CONFIRM,
        "online": CONFIRM,
        "iniciando": WARNING,
        "indisponível": PASTEL_BLUE,
        "inválido": CANCEL,
        "com erro": CANCEL,
    }.get(status, PASTEL_BLUE)
    return ft.Container(
        height=30,
        padding=ft.Padding(left=12, top=0, right=12, bottom=0),
        alignment=ft.Alignment.CENTER,
        bgcolor=color,
        border_radius=8,
        content=ft.Text(
            status.capitalize(),
            size=12,
            weight=ft.FontWeight.W_700,
            color=TEXT_PRIMARY,
        ),
    )
