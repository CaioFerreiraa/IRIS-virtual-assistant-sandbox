from __future__ import annotations

import flet as ft

from ui.theme.colors import (
    CANCEL,
    CONFIRM,
    PASTEL_BLUE,
    TEXT_PRIMARY,
    WARNING,
)


def build_status_chip(status: str, *, height: int = 40) -> ft.Container:
    color = {
        "disponível": CONFIRM,
        "online": CONFIRM,
        "sucesso": CONFIRM,
        "iniciando": WARNING,
        "executando": WARNING,
        "indisponível": PASTEL_BLUE,
        "inválido": CANCEL,
        "com erro": CANCEL,
        "erro": CANCEL,
    }.get(status, PASTEL_BLUE)
    return ft.Container(
        height=height,
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
