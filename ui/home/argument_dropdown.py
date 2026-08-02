from collections.abc import Callable, Mapping, Sequence

import flet as ft
import ui.home as ui

from ui.theme.colors import PASTEL_BLUE, PASTEL_PURPLE, TEXT_PRIMARY, TEXT_SECONDARY


ArgumentOption = str | Mapping[str, object]


def argument_label(argument_option: ArgumentOption) -> str:
    # Extrai o texto que aparece para uma opcao de argumento.
    if isinstance(argument_option, str):
        return argument_option
    return str(argument_option.get("label", argument_option.get("value", "")))


def argument_value(argument_option: ArgumentOption) -> str:
    # Extrai o valor enviado ao modulo para uma opcao de argumento.
    if isinstance(argument_option, str):
        return argument_option
    return str(argument_option.get("value", argument_option.get("label", "")))


def argument_description(argument_option: ArgumentOption) -> str:
    # Extrai a descricao complementar de uma opcao de argumento.
    if isinstance(argument_option, str):
        return ""
    return str(argument_option.get("description", ""))


def build_argument_panel_content(argument_input_field: ft.TextField, arguments_list: ft.ListView) -> ft.Column:
    # Agrupa o input de argumentos com a lista de argumentos encontrados.
    return ft.Column(
        spacing=8,
        tight=True,
        controls=[
            argument_input_field,
            ft.Container(expand=True, content=arguments_list),
        ],
    )


def build_argument_suggestion_controls(
    arguments: Sequence[ArgumentOption],
    on_select: Callable[[str], None],
) -> list[ft.Control]:
    # Cria os controles da lista de argumentos encontrados.
    return [
        _build_argument_leaf(argument, on_select)
        for argument in sorted(arguments, key=lambda item: ui.text_utils.normalize(argument_label(item)))
    ]


def _build_argument_leaf(argument: ArgumentOption, on_select: Callable[[str], None]) -> ft.Container:
    # Cria uma linha selecionavel para um argumento.
    label = argument_label(argument)
    value = argument_value(argument)
    description = argument_description(argument)

    return ft.Container(
        height=42,
        padding=ft.Padding(left=12, top=0, right=12, bottom=0),
        border_radius=12,
        ink=True,
        ink_color=PASTEL_BLUE,
        on_click=lambda _, selected=value: on_select(selected),
        content=ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon=ft.Icons.INSERT_DRIVE_FILE_ROUNDED, size=18, color=PASTEL_PURPLE),
                ft.Text(label, size=14, color=TEXT_PRIMARY, overflow=ft.TextOverflow.ELLIPSIS, no_wrap=True, expand=True),
                ft.Text(description, size=12, color=TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS, no_wrap=True),
            ],
        ),
    )
