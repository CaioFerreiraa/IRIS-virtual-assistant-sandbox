from __future__ import annotations

import flet as ft

from ui.theme.colors import BORDER, BLUE_GREY, TEXT_PRIMARY, TEXT_SECONDARY


def build_general_settings_tab() -> ft.Container:
    return ft.Container(
        padding=24,
        bgcolor=BLUE_GREY,
        border=ft.Border.all(1, BORDER),
        border_radius=8,
        content=ft.Column(
            tight=True,
            spacing=6,
            controls=[
                ft.Text("Configurações gerais", size=18, weight=ft.FontWeight.W_700, color=TEXT_PRIMARY),
                ft.Text("Esta seção será disponibilizada em uma próxima etapa.", size=14, color=TEXT_SECONDARY),
            ],
        ),
    )
