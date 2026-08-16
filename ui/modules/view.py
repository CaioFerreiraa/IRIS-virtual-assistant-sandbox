from __future__ import annotations

import flet as ft

from database.db import SessionLocal
from services.module_service import (
    get_module_detail,
    save_auto_start_preference,
    save_custom_call_name,
    save_module_variable_values,
)
from ui.shared.components.form_controls import build_primary_button, build_text_field
from ui.shared.components.route_content_container import build_route_content_container
from ui.shared.components.toaster_handler import ToasterHandler
from ui.theme.colors import (
    BORDER,
    CANCEL,
    CONFIRM,
    PASTEL_BLUE,
    PASTEL_DARK_PURPLE,
    PASTEL_PURPLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
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
        )
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
        self.custom_call_name_field = build_text_field(
            "Nome de chamada personalizado",
            str(detail["custom_call_name"]),
            helper="Opcional. Substitui o nome personalizado anterior.",
            disabled=not bool(detail["is_available"]),
        )
        self.variable_fields: dict[str, ft.TextField] = {}

    def build(self) -> ft.Container:
        return build_route_content_container(
            icon=ft.Icons.EXTENSION_ROUNDED,
            title=str(self.detail["name"]),
            subtitle=self._build_breadcrumb(),
            trailing=self._build_header_trailing(),
            content=ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=18,
                controls=[
                    self._build_about_card(),
                    self._build_call_name_card(),
                    self._build_settings_card(),
                ],
            )
        )

    def _build_header_trailing(self) -> ft.Row:
        status = str(self.detail["status"])
        controls: list[ft.Control] = [_build_status_chip(status)]
        if bool(self.detail["can_auto_start"]):
            controls.append(
                ft.Row(
                    tight=True,
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(
                            "Iniciar com a IRIS",
                            size=13,
                            weight=ft.FontWeight.W_600,
                            color=TEXT_PRIMARY,
                        ),
                        ft.Switch(
                            value=bool(self.detail["auto_start_enabled"]),
                            active_color=PASTEL_DARK_PURPLE,
                            active_track_color=PASTEL_PURPLE,
                            on_change=self.on_auto_start_change,
                        ),
                    ],
                )
            )
        return ft.Row(
            tight=True,
            spacing=16,
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

    def _build_about_card(self) -> ft.Container:
        readme_error = str(self.detail["readme_error"])
        if readme_error:
            content: ft.Control = ft.Container(
                padding=ft.Padding.all(14),
                border_radius=8,
                bgcolor=PASTEL_BLUE,
                content=ft.Text(readme_error, size=13, color=TEXT_PRIMARY),
            )
        else:
            content = ft.Markdown(
                str(self.detail["readme_content"]),
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                code_theme=ft.MarkdownCodeTheme.A11Y_LIGHT,
                auto_follow_links=False,
            )
        return _build_card("Sobre o módulo", content)

    def _build_call_name_card(self) -> ft.Container:
        original_field = build_text_field(
            "Nome de chamada original",
            str(self.detail["call_name"]),
            helper="Definido pelo desenvolvedor no module.json.",
            disabled=True,
        )
        controls: list[ft.Control] = [
            ft.Row(spacing=14, controls=[original_field, self.custom_call_name_field]),
        ]
        if bool(self.detail["is_available"]):
            controls.append(
                ft.Row(
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        build_primary_button(
                            "Salvar nome personalizado",
                            self.on_save_custom_call_name,
                        )
                    ],
                )
            )
        return _build_card(
            "Nome de chamada",
            ft.Column(spacing=14, controls=controls),
        )

    def _build_settings_card(self) -> ft.Container:
        editable_variables = [
            variable
            for variable in list(self.detail["variables"])
            if bool(variable["user_editable"])
        ]
        if not editable_variables:
            return _build_card(
                "Configurações",
                ft.Text(
                    "Este módulo não possui configurações editáveis.",
                    size=13,
                    color=TEXT_SECONDARY,
                ),
            )

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

        if bool(self.detail["is_available"]):
            fields.append(
                ft.Row(
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        build_primary_button(
                            "Salvar configurações",
                            self.on_save_variables,
                        )
                    ],
                )
            )
        return _build_card("Configurações", ft.Column(spacing=14, controls=fields))

    def on_save_custom_call_name(self, event: ft.ControlEvent) -> None:
        try:
            save_custom_call_name(
                int(self.detail["id"]),
                self.custom_call_name_field.value,
                self.session_factory,
            )
        except Exception as error:
            self._show_error(str(error))
            return
        self._show_success("Nome de chamada personalizado salvo.")

    def on_save_variables(self, event: ft.ControlEvent) -> None:
        del event
        values = {
            key: field.value or ""
            for key, field in self.variable_fields.items()
        }
        try:
            save_module_variable_values(
                int(self.detail["id"]),
                values,
                self.session_factory,
            )
        except Exception as error:
            self._show_error(str(error))
            return
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
            event.control.update()
            self._show_error(str(error))
            return
        self._show_success(
            "Preferência de inicialização atualizada para a próxima abertura da IRIS."
        )

    def _show_success(self, message: str) -> None:
        if self.toaster_handler is not None:
            self.toaster_handler.show_success(message)

    def _show_error(self, message: str) -> None:
        if self.toaster_handler is not None:
            self.toaster_handler.show_error(message)


def _build_card(title: str, content: ft.Control) -> ft.Container:
    return ft.Container(
        padding=ft.Padding(left=18, top=16, right=18, bottom=18),
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
