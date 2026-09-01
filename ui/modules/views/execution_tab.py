from __future__ import annotations

import json

import flet as ft

from ui.shared.components.form_controls import (
    build_dropdown,
    build_floating_save_bar,
    build_secondary_button,
    build_text_field,
)
from ui.shared.components.tooltip_container import build_tooltip_container
from ui.theme.colors import (
    BORDER,
    PASTEL_BLUE,
    PASTEL_DARK_PURPLE,
    SURFACE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


HTTP_METHOD_OPTIONS = tuple(
    (method, method)
    for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
)
BODY_MODE_OPTIONS = (
    ("none", "Sem corpo"),
    ("raw_json", "JSON bruto"),
    ("raw_text", "Texto bruto"),
    ("form_urlencoded", "Formulário URL encoded"),
)


class ModuleExecutionTabMixin:
    def _build_execution_tab(self) -> ft.Stack:
        self.execution_save_bar = None
        controls: list[ft.Control] = [self._build_argument_section()]
        if not bool(self.detail["is_available"]):
            controls.append(self._build_unavailable_notice())

        if self.http_request is not None:
            controls.extend(
                [
                    self._build_http_request_row(),
                    self._build_http_definition_tabs(),
                ]
            )

        can_save_request = bool(
            self.http_request is not None
            and self.detail["is_available"]
        )
        stack_controls: list[ft.Control] = [
            ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=16,
                controls=[
                    *controls,
                    ft.Container(height=74) if can_save_request else ft.Container(),
                ],
            )
        ]
        if can_save_request:
            self.execution_state_saved = self._current_execution_values()
            self.execution_state_edited = None
            self.execution_save_bar = build_floating_save_bar(
                "Salvar requisição",
                self.on_save_execution,
                visible=False,
            )
            stack_controls.append(self.execution_save_bar)

        return ft.Stack(expand=True, controls=stack_controls)

    def on_execution_form_change(
        self,
        event: ft.ControlEvent | None = None,
    ) -> None:
        del event
        self.execution_state_edited = self._current_execution_values()
        self._sync_execution_save_bar_visibility()

    def on_http_argument_enabled_change(self, event: ft.ControlEvent) -> None:
        enabled = bool(event.control.value)
        self.argument_explanation = (
            "Informe a string que substituirá {{argument}} na requisição."
            if enabled
            else "Este módulo não utiliza argumento de execução."
        )
        self.argument_field.disabled = (
            not bool(self.detail["is_available"])
            or not enabled
        )
        self.argument_field.helper = self.argument_explanation
        self.argument_field.tooltip = build_tooltip_container(
            self.argument_explanation
        )
        self._update_if_mounted(self.argument_field)
        self.on_execution_form_change()

    def _current_execution_values(self) -> dict[str, object]:
        if self.http_request is None:
            return {"argument": self.argument_field.value or ""}
        return {
            "method": self.http_method_field.value or "",
            "url": self.http_url_field.value or "",
            "argument_enabled": bool(self.http_argument_enabled_switch.value),
            "argument": self.argument_field.value or "",
            "params_json": json.dumps(
                self._http_item_values(self.http_param_rows),
                ensure_ascii=False,
            ),
            "authorization_json": json.dumps(
                {"type": self.http_authorization_field.value or "none"},
                ensure_ascii=False,
            ),
            "headers_json": json.dumps(
                self._http_item_values(self.http_header_rows),
                ensure_ascii=False,
            ),
            "body_mode": self.http_body_mode_field.value or "none",
            "body_content": self.http_body_content_field.value or "",
            "pre_request": self.http_pre_request_field.value or "",
            "post_response": self.http_post_response_field.value or "",
        }

    def _reset_execution_save_state(self) -> None:
        self.execution_state_saved = self._current_execution_values()
        self.execution_state_edited = None
        self._sync_execution_save_bar_visibility()

    def _sync_execution_save_bar_visibility(self) -> None:
        if self.execution_save_bar is None:
            return
        has_changes = (
            bool(self.detail["is_available"])
            and self.execution_state_edited is not None
            and self.execution_state_saved != self.execution_state_edited
        )
        if self.execution_save_bar.is_visible == has_changes:
            return
        self.execution_save_bar.update_visibility(has_changes)

    def _build_unavailable_notice(self) -> ft.Container:
        message = str(self.detail.get("validation_error") or "")
        if not message:
            message = "O módulo está indisponível e não pode ser executado."
        return ft.Container(
            width=float("inf"),
            padding=14,
            bgcolor=PASTEL_BLUE,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            content=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(
                        ft.Icons.INFO_OUTLINE_ROUNDED,
                        size=20,
                        color=PASTEL_DARK_PURPLE,
                    ),
                    ft.Text(message, expand=True, size=13, color=TEXT_PRIMARY),
                ],
            ),
        )

    def _build_http_request_row(self) -> ft.Container:
        is_available = bool(self.detail["is_available"])
        self.http_method_field = build_dropdown(
            "Método",
            str(self.http_request["method"]),
            HTTP_METHOD_OPTIONS,
            disabled=not is_available,
            on_select=self.on_execution_form_change,
        )
        self.http_url_field = build_text_field(
            "URL",
            str(self.http_request["url"]),
            disabled=not is_available,
        )
        self.http_url_field.on_change = self.on_execution_form_change
        restore_button = build_secondary_button(
            "Resetar",
            self.on_restore_http_request,
            disabled=not is_available,
            tooltip="Voltar ao padrão do module.json",
        )
        self.http_method_field.col = {"sm": 12, "md": 2}
        self.http_url_field.col = {"sm": 12, "md": 6}
        restore_button.col = {"sm": 12, "md": 2}
        self.execute_button.col = {"sm": 12, "md": 2}
        return self._build_execution_section(
            "Requisição HTTP",
            "A definição pode ser personalizada e restaurada a partir do module.json.",
            ft.ResponsiveRow(
                spacing=12,
                run_spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    self.http_method_field,
                    self.http_url_field,
                    restore_button,
                    self.execute_button,
                ],
            ),
        )

    def _build_argument_section(self) -> ft.Container:
        content: ft.Control = self.argument_field
        if self.http_request is not None:
            self.http_argument_enabled_switch = ft.Switch(
                label="Utilizar argumento na requisição",
                value=bool(self.http_request["argument_enabled"]),
                disabled=not bool(self.detail["is_available"]),
                on_change=self.on_http_argument_enabled_change,
                active_color=PASTEL_DARK_PURPLE,
            )
            self.argument_field.on_change = self.on_execution_form_change
            content = ft.Column(
                spacing=10,
                controls=[
                    self.http_argument_enabled_switch,
                    self.argument_field,
                ],
            )
        return self._build_execution_section(
            "Argumento da execução",
            self.argument_explanation,
            content,
        )

    def _build_http_definition_tabs(self) -> ft.Container:
        return ft.Container(
            width=float("inf"),
            height=430,
            bgcolor=SURFACE,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Tabs(
                length=5,
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
                                ft.Tab(label="Parâmetros"),
                                ft.Tab(label="Autorização"),
                                ft.Tab(label="Cabeçalhos"),
                                ft.Tab(label="Corpo"),
                                ft.Tab(label="Scripts"),
                            ],
                        ),
                        ft.TabBarView(
                            expand=True,
                            controls=[
                                self._build_http_items_view(
                                    "params",
                                    list(self.http_request["params"]),
                                    "Nenhum parâmetro configurado.",
                                ),
                                self._build_authorization_view(),
                                self._build_http_items_view(
                                    "headers",
                                    list(self.http_request["headers"]),
                                    "Nenhum cabeçalho configurado.",
                                ),
                                self._build_body_view(),
                                self._build_scripts_view(),
                            ],
                        ),
                    ],
                ),
            ),
        )

    def _build_http_items_view(
        self,
        field_name: str,
        items: list[dict[str, object]],
        empty_message: str,
    ) -> ft.Container:
        rows = [
            self._build_http_item_row(field_name, item)
            for item in items
        ]
        rows_container = ft.Column(
            spacing=10,
            controls=[row["control"] for row in rows],
        )
        empty_text = ft.Text(
            empty_message,
            visible=not rows,
            size=12,
            color=TEXT_SECONDARY,
        )
        if field_name == "params":
            self.http_param_rows = rows
            self.http_params_rows_container = rows_container
            self.http_params_empty_text = empty_text
            add_label = "Adicionar parâmetro"
        else:
            self.http_header_rows = rows
            self.http_headers_rows_container = rows_container
            self.http_headers_empty_text = empty_text
            add_label = "Adicionar cabeçalho"
        add_button = build_secondary_button(
            add_label,
            lambda event, name=field_name: self._add_http_item(event, name),
            disabled=not bool(self.detail["is_available"]),
        )
        return ft.Container(
            expand=True,
            padding=14,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                spacing=10,
                controls=[
                    ft.Text(
                        "Edite somente os itens necessários. O placeholder {{argument}} é permitido.",
                        size=12,
                        color=TEXT_SECONDARY,
                    ),
                    empty_text,
                    rows_container,
                    ft.Row(controls=[add_button]),
                ],
            ),
        )

    def _build_http_item_row(
        self,
        field_name: str,
        item: dict[str, object],
    ) -> dict[str, object]:
        is_available = bool(self.detail["is_available"])
        enabled = ft.Switch(
            label="Ativo",
            value=bool(item.get("enabled")),
            disabled=not is_available,
            on_change=self.on_execution_form_change,
            active_color=PASTEL_DARK_PURPLE,
        )
        key_field = build_text_field(
            "Chave",
            str(item.get("key") or ""),
            disabled=not is_available,
        )
        value_field = build_text_field(
            "Valor",
            str(item.get("value") or ""),
            disabled=not is_available,
        )
        description_field = build_text_field(
            "Descrição",
            str(item.get("description") or ""),
            disabled=not is_available,
        )
        for field in (key_field, value_field, description_field):
            field.on_change = self.on_execution_form_change
        remove_button = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
            tooltip="Remover item",
            disabled=not is_available,
            icon_color=TEXT_SECONDARY,
        )
        enabled.col = {"sm": 12, "md": 1}
        key_field.col = {"sm": 12, "md": 3}
        value_field.col = {"sm": 12, "md": 3}
        description_field.col = {"sm": 12, "md": 4}
        remove_button.col = {"sm": 12, "md": 1}
        row_state: dict[str, object] = {
            "enabled": enabled,
            "key": key_field,
            "value": value_field,
            "description": description_field,
        }
        remove_button.on_click = (
            lambda event, name=field_name, row=row_state: self._remove_http_item(
                event,
                name,
                row,
            )
        )
        row_state["control"] = ft.ResponsiveRow(
            spacing=8,
            run_spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                enabled,
                key_field,
                value_field,
                description_field,
                remove_button,
            ],
        )
        return row_state

    def _add_http_item(
        self,
        event: ft.ControlEvent | None,
        field_name: str,
    ) -> None:
        del event
        rows, container, empty_text = self._http_item_controls(field_name)
        row = self._build_http_item_row(
            field_name,
            {"key": "", "value": "", "description": "", "enabled": True},
        )
        rows.append(row)
        container.controls.append(row["control"])
        empty_text.visible = False
        self._update_if_mounted(container)
        self._update_if_mounted(empty_text)
        self.on_execution_form_change()

    def _remove_http_item(
        self,
        event: ft.ControlEvent | None,
        field_name: str,
        row: dict[str, object],
    ) -> None:
        del event
        rows, container, empty_text = self._http_item_controls(field_name)
        if row not in rows:
            return
        rows.remove(row)
        container.controls = [current["control"] for current in rows]
        empty_text.visible = not rows
        self._update_if_mounted(container)
        self._update_if_mounted(empty_text)
        self.on_execution_form_change()

    def _http_item_controls(
        self,
        field_name: str,
    ) -> tuple[list[dict[str, object]], ft.Column, ft.Text]:
        if field_name == "params":
            return (
                self.http_param_rows,
                self.http_params_rows_container,
                self.http_params_empty_text,
            )
        return (
            self.http_header_rows,
            self.http_headers_rows_container,
            self.http_headers_empty_text,
        )

    @staticmethod
    def _http_item_values(
        rows: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        return [
            {
                "key": row["key"].value or "",
                "value": row["value"].value or "",
                "description": row["description"].value or "",
                "enabled": bool(row["enabled"].value),
            }
            for row in rows
        ]

    def _build_authorization_view(self) -> ft.Container:
        self.http_authorization_field = build_dropdown(
            "Tipo de autorização",
            str(self.http_request["authorization"].get("type") or "none"),
            (("none", "Sem autenticação"),),
            helper="Credenciais não são suportadas nesta versão.",
            disabled=not bool(self.detail["is_available"]),
            on_select=self.on_execution_form_change,
        )
        return ft.Container(
            expand=True,
            padding=14,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                spacing=10,
                controls=[
                    ft.Text(
                        "Sem autenticação",
                        size=15,
                        weight=ft.FontWeight.W_600,
                        color=TEXT_PRIMARY,
                    ),
                    ft.Text(
                        "Credenciais continuam não suportadas e não podem ser salvas.",
                        size=12,
                        color=TEXT_SECONDARY,
                    ),
                    self.http_authorization_field,
                ],
            ),
        )

    def _build_body_view(self) -> ft.Container:
        body = dict(self.http_request["body"])
        content = body["content"]
        content_text = (
            json.dumps(content, ensure_ascii=False, indent=2)
            if not isinstance(content, str)
            else content
        )
        self.http_body_mode_field = build_dropdown(
            "Modo",
            str(body["mode"]),
            BODY_MODE_OPTIONS,
            disabled=not bool(self.detail["is_available"]),
            on_select=self.on_execution_form_change,
        )
        self.http_body_content_field = build_text_field(
            "Conteúdo",
            content_text,
            helper=(
                "No modo form_urlencoded, informe uma lista JSON de itens. "
                "Nos demais modos, informe texto."
            ),
            multiline=True,
            disabled=not bool(self.detail["is_available"]),
        )
        self.http_body_content_field.min_lines = 6
        self.http_body_content_field.max_lines = 9
        self.http_body_content_field.on_change = self.on_execution_form_change
        return ft.Container(
            expand=True,
            padding=14,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                spacing=12,
                controls=[
                    self.http_body_mode_field,
                    self.http_body_content_field,
                ],
            ),
        )

    def _build_scripts_view(self) -> ft.Container:
        scripts = dict(self.http_request["scripts"])
        self.http_pre_request_field = build_text_field(
            "Pré-requisição",
            str(scripts["pre_request"]),
            multiline=True,
            disabled=not bool(self.detail["is_available"]),
        )
        self.http_post_response_field = build_text_field(
            "Pós-resposta",
            str(scripts["post_response"]),
            multiline=True,
            disabled=not bool(self.detail["is_available"]),
        )
        self.http_pre_request_field.on_change = self.on_execution_form_change
        self.http_post_response_field.on_change = self.on_execution_form_change
        return ft.Container(
            expand=True,
            padding=14,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                spacing=12,
                controls=[
                    ft.Text(
                        "Scripts são exibidos, mas não são executados nesta versão.",
                        size=13,
                        color=TEXT_SECONDARY,
                    ),
                    self.http_pre_request_field,
                    self.http_post_response_field,
                ],
            ),
        )

    def _build_execution_section(
        self,
        title: str,
        description: str,
        content: ft.Control,
    ) -> ft.Container:
        return ft.Container(
            width=float("inf"),
            padding=18,
            bgcolor=SURFACE,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Column(
                        tight=True,
                        spacing=4,
                        controls=[
                            ft.Text(
                                title,
                                size=17,
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
