from __future__ import annotations

import flet as ft

from ui.modules.components.card import build_card
from ui.shared.components.form_controls import (
    build_floating_save_bar,
    build_text_field,
)
from ui.shared.components.tooltip_container import build_tooltip_container
from ui.theme.colors import (
    BLUE_GREY,
    BORDER,
    PASTEL_DARK_PURPLE,
    PASTEL_PURPLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


FIELD_HELP = {
    "call_name": "Nome definido pelo manifesto do módulo. Ele não pode ser alterado pela interface.",
    "custom_call_name": "Nome opcional escolhido pelo usuário para substituir o nome de chamada original.",
    "argument": "Valor transitório enviado somente na próxima execução do módulo.",
    "auto_start": "Define se o módulo raiz deve iniciar automaticamente na abertura da IRIS.",
}


class ModuleSettingsTabMixin:
    def _build_settings_tab(self) -> ft.Stack:
        controls: list[ft.Control] = [
            self._build_quick_settings_section(),
            self._build_model_data_section(),
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
                build_card(
                    "Variáveis da requisição",
                    ft.Column(spacing=14, controls=fields),
                )
            )

        controls.append(ft.Container(height=74))

        content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=16,
            controls=controls,
        )
        return ft.Stack(
            expand=True,
            controls=[
                content,
                build_floating_save_bar(
                    "Salvar configurações",
                    self.on_save_settings,
                    visible=bool(self.detail["is_available"]),
                ),
            ],
        )

    def _build_quick_settings_section(self) -> ft.Container:
        controls = [
            self._build_field_wrapper(
                self._build_call_name_field(),
                FIELD_HELP["call_name"],
            ),
            self._build_field_wrapper(
                self.custom_call_name_field,
                FIELD_HELP["custom_call_name"],
            ),
            self._build_field_wrapper(
                self._build_argument_field(),
                FIELD_HELP["argument"],
            ),
        ]

        auto_start_field = self._build_auto_start_field()
        if auto_start_field is not None:
            controls.append(
                self._build_field_wrapper(
                    auto_start_field,
                    FIELD_HELP["auto_start"],
                )
            )

        return self._form_section(
            "Configurações",
            "Ajuste a chamada do módulo e os valores usados na execução.",
            [self._field_grid(*controls)],
        )

    def _build_model_data_section(self) -> ft.Container:
        fields = [
            self._build_model_field(label, value)
            for label, value in list(self.detail["model_data"])
            if label not in {
                "Nome de chamada original",
                "Nome de chamada personalizado",
                "Iniciar com a IRIS",
            }
        ]
        rows = [
            self._field_grid(*fields[index:index + 2])
            for index in range(0, len(fields), 2)
        ]
        return self._form_section(
            "Dados do módulo",
            "Campos persistidos do módulo em modo de leitura.",
            rows,
        )

    def _build_call_name_field(self) -> ft.TextField:
        field = build_text_field(
            "Nome de chamada original",
            str(self.detail["call_name"]),
            disabled=True,
        )
        self.model_value_controls["Nome de chamada original"] = field
        return field

    def _build_argument_field(self) -> ft.Control:
        if self.argument_field is not None:
            return self.argument_field
        return build_text_field(
            "Argumento da execução",
            "",
            helper="Este módulo não solicita argumento de execução.",
            disabled=True,
        )

    def _build_auto_start_field(self) -> ft.Container | None:
        if not bool(self.detail.get("is_root_module", False)):
            return None

        can_auto_start = bool(self.detail["can_auto_start"])
        if can_auto_start:
            explanation = "A alteração será aplicada na próxima abertura da IRIS."
        elif not bool(self.detail["is_available"]):
            explanation = "A inicialização automática fica indisponível enquanto o módulo estiver com erro."
        elif bool(self.detail["supports_auto_start"]):
            explanation = "A inicialização automática está indisponível para este runtime."
        else:
            explanation = "O desenvolvedor deste módulo não declarou suporte à inicialização automática."

        return ft.Container(
            expand=True,
            height=58,
            padding=ft.Padding(left=12, top=0, right=12, bottom=0),
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            alignment=ft.Alignment.CENTER_LEFT,
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(
                        expand=True,
                        tight=True,
                        spacing=2,
                        controls=[
                            ft.Text(
                                "Iniciar com a IRIS",
                                size=13,
                                color=TEXT_PRIMARY,
                            ),
                            ft.Text(
                                explanation,
                                size=11,
                                color=TEXT_SECONDARY,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                tooltip=explanation,
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

    def _build_model_field(self, label: str, value: str) -> ft.Container:
        field = build_text_field(label, value, disabled=True)
        field.tooltip = value
        self.model_value_controls[label] = field
        return self._build_field_wrapper(field, value or label)

    def _form_section(
        self,
        title: str,
        description: str,
        controls: list[ft.Control],
    ) -> ft.Container:
        return ft.Container(
            padding=20,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            content=ft.Column(
                spacing=22,
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
                    *controls,
                ],
            ),
        )

    def _field_grid(self, *controls: ft.Control) -> ft.ResponsiveRow:
        return ft.ResponsiveRow(
            spacing=18,
            run_spacing=24,
            controls=list(controls),
        )

    def _build_field_wrapper(
        self,
        field: ft.Control,
        help_text: str,
        *,
        md_columns: int = 6,
    ) -> ft.Container:
        return ft.Container(
            expand=True,
            col={"sm": 12, "md": md_columns},
            content=ft.Row(
                expand=True,
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(expand=True, content=field),
                    ft.Container(
                        width=25,
                        height=25,
                        border_radius=20,
                        alignment=ft.Alignment.CENTER,
                        bgcolor=BLUE_GREY,
                        tooltip=build_tooltip_container(help_text),
                        content=ft.Icon(
                            ft.Icons.INFO_OUTLINE_ROUNDED,
                            color=PASTEL_PURPLE,
                            size=15,
                        ),
                    ),
                ],
            ),
        )
