from __future__ import annotations

import flet as ft

from ui.theme.colors import SURFACE, TEXT_PRIMARY
from ui.theme.fonts import TITLE_FONT
from ui.theme.colors import PASTEL_DARK_PURPLE

def build_card(title: str | None, content: ft.Control) -> ft.Container:
    return ft.Container(
        padding=ft.Padding(left=18, top=16, right=18, bottom=18),
        bgcolor=SURFACE,
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Text(
                    title or '',
                    size=17,
                    weight=ft.FontWeight.BOLD,
                    color=PASTEL_DARK_PURPLE,
                    font_family=TITLE_FONT,
                ),
                content,
            ],
        ),
    )
