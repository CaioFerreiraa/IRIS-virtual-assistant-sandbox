from __future__ import annotations

import flet as ft

from ui.shared.components.route_content_container import build_route_content_container
from ui.theme.colors import PASTEL_DARK_PURPLE, TEXT_PRIMARY


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
