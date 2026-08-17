from __future__ import annotations

import flet as ft

from ui.theme.colors import (
    BLUE_GREY,
    BORDER,
    PASTEL_DARK_PURPLE,
    SURFACE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.theme.fonts import TITLE_FONT


HeaderValue = str | ft.Control
HeaderIcon = ft.IconData | ft.Control


def build_route_content_container(
    content: ft.Control,
    *,
    icon: HeaderIcon | None = None,
    title: HeaderValue | None = None,
    subtitle: HeaderValue | None = None,
    trailing: ft.Control | None = None,
    expand: bool = True,
) -> ft.Container:
    """Constrói o shell visual comum das rotas da IRIS.

    `content` é o único argumento obrigatório. Os elementos do cabeçalho são
    opcionais e o cabeçalho inteiro é omitido quando nenhum deles é informado.
    """
    controls: list[ft.Control] = []
    header = _build_route_header(icon, title, subtitle, trailing)
    if header is not None:
        controls.append(header)
    controls.append(ft.Container(expand=expand, content=content))

    return ft.Container(
        expand=expand,
        margin=ft.Margin(left=16, top=28, right=22, bottom=25),
        padding=ft.Padding(left=14, top=16, right=20, bottom=18),
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=12,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Column(
            expand=expand,
            tight=not expand,
            spacing=16,
            controls=controls,
        ),
    )


def _build_route_header(
    icon: HeaderIcon | None,
    title: HeaderValue | None,
    subtitle: HeaderValue | None,
    trailing: ft.Control | None,
) -> ft.Row | None:
    if icon is None and title is None and subtitle is None and trailing is None:
        return None

    controls: list[ft.Control] = []
    if icon is not None:
        controls.append(
            ft.Container(
                width=42,
                height=42,
                border_radius=8,
                alignment=ft.Alignment.CENTER,
                bgcolor=BLUE_GREY,
                content=(
                    icon
                    if isinstance(icon, ft.Control)
                    else ft.Icon(
                        icon=icon,
                        size=22,
                        color=PASTEL_DARK_PURPLE,
                    )
                ),
            )
        )

    title_controls: list[ft.Control] = []
    if title is not None:
        title_controls.append(_build_header_value(title, is_title=True))
    if subtitle is not None:
        title_controls.append(_build_header_value(subtitle, is_title=False))
    controls.append(
        ft.Column(
            spacing=2,
            tight=True,
            expand=True,
            controls=title_controls,
        )
    )
    if trailing is not None:
        controls.append(trailing)

    return ft.Row(
        spacing=16,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=controls,
    )


def _build_header_value(value: HeaderValue, *, is_title: bool) -> ft.Control:
    if isinstance(value, ft.Control):
        return value
    if is_title:
        return ft.Text(
            value,
            size=24,
            weight=ft.FontWeight.BOLD,
            color=TEXT_PRIMARY,
            font_family=TITLE_FONT,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
    return ft.Text(
        value,
        size=13,
        color=TEXT_SECONDARY,
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
