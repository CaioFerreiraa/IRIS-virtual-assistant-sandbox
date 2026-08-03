from collections.abc import Callable, Sequence

import flet as ft

from ui.theme.colors import (
    BORDER,
    PASTEL_BLUE,
    PASTEL_PURPLE,
    SURFACE,
    BLUE_GREY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


DEFAULT_MODULES = (
    "Assistente",
    "Agenda",
    "Arquivos",
    "Navegador",
    "Sistema",
)


def _module_item(
    name: str,
    is_active: bool,
    on_select: Callable[[str], None],
) -> ft.Container:
    return ft.Container(
        height=44,
        padding=ft.Padding(left=12, top=0, right=12, bottom=0),
        alignment=ft.Alignment.CENTER_LEFT,
        bgcolor=PASTEL_BLUE if is_active else BLUE_GREY,
        border=ft.Border.all(1, PASTEL_PURPLE if is_active else BORDER),
        border_radius=8,
        ink=True,
        ink_color=PASTEL_PURPLE,
        on_click=lambda _: on_select(name),
        content=ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=10,
                    height=10,
                    border_radius=5,
                    bgcolor=PASTEL_PURPLE if is_active else PASTEL_BLUE,
                ),
                ft.Text(
                    name,
                    size=14,
                    color=TEXT_PRIMARY if is_active else TEXT_SECONDARY,
                    weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_500,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    no_wrap=True,
                    tooltip=name,
                ),
            ],
        ),
    )


def build_sidebar(
    active_module: str,
    on_select: Callable[[str], None],
    modules: Sequence[str] | None = None,
) -> ft.Container:
    module_names = tuple(modules or DEFAULT_MODULES)

    return ft.Container(
        width=248,
        expand=True,
        margin=ft.Padding(left=16, top=28, right=16, bottom=28),
        padding=ft.Padding(left=16, top=18, right=16, bottom=18),
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=16,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Text(
                    "Módulos",
                    size=13,
                    weight=ft.FontWeight.BOLD,
                    color=TEXT_SECONDARY,
                ),
                ft.Column(
                    spacing=8,
                    controls=[
                        _module_item(name, name == active_module, on_select)
                        for name in module_names
                    ],
                ),
            ],
        ),
    )
