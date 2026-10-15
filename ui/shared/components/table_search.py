import unicodedata
from collections.abc import Callable

import flet as ft

from ui.theme.colors import (
    BLUE_GREY, BORDER, PASTEL_DARK_PURPLE, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY,
)


def build_table_search_input(
    hint: str,
    on_change: Callable[[ft.ControlEvent], None],
) -> ft.TextField:
    return ft.TextField(
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        hint_text=hint,
        text_style=ft.TextStyle(size=12, color=TEXT_PRIMARY),
        hint_style=ft.TextStyle(size=12, color=TEXT_SECONDARY),
        border_color=BORDER,
        focused_border_color=BLUE_GREY,
        cursor_color=PASTEL_DARK_PURPLE,
        border_radius=8,
        dense=True,
        expand=True,
        on_change=on_change,
    )


def build_table_search_bar(
    search_input: ft.TextField,
    on_clear: Callable[[ft.ControlEvent], None],
) -> ft.Container:
    return ft.Container(
        bgcolor=SURFACE,
        padding=ft.Padding(left=10, top=8, right=10, bottom=8),
        content=ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                search_input,
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_size=18,
                    icon_color=TEXT_SECONDARY,
                    tooltip="Limpar pesquisa",
                    on_click=on_clear,
                ),
            ],
        ),
    )


def normalize_search_text(value: str) -> str:
    normalized_value = unicodedata.normalize("NFD", value.lower())
    chars: list[str] = []
    for char in normalized_value:
        if unicodedata.category(char) == "Mn":
            continue
        if char.isalnum() or char.isspace():
            chars.append(char)
        elif char not in "-_":
            chars.append(" ")
    return " ".join("".join(chars).split())
