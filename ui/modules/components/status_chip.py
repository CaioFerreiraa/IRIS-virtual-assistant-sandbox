from __future__ import annotations

import flet as ft

from ui.theme.colors import (
    CANCEL,
    CONFIRM,
    PASTEL_BLUE,
    TEXT_PRIMARY,
    WARNING,
)


def build_status_chip(status: str) -> ft.Container:
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
