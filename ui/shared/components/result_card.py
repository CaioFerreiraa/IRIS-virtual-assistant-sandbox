from __future__ import annotations

import json
from collections.abc import Mapping

import flet as ft

from ui.theme.colors import (
    BLUE_GREY,
    BORDER,
    CANCEL,
    CONFIRM,
    PASTEL_BLUE,
    PASTEL_DARK_PURPLE,
    SURFACE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)


ControlDimension = int | float | None

DEFAULT_RESULT_CARD_HEIGHT = 180
DEFAULT_RESULT_CARD_WIDTH = float("inf")
DEFAULT_RESULT_CARD_COLLAPSED_HEIGHT = 62
DEFAULT_RESULT_BODY_WIDTH = float("inf")


def build_result_card(
    status: str,
    result: Mapping[str, object],
    *,
    title: str = "Resultado da execução",
    body_title: str = "Corpo de retorno",
    height: ControlDimension = DEFAULT_RESULT_CARD_HEIGHT,
    width: ControlDimension = DEFAULT_RESULT_CARD_WIDTH,
    collapsed_height: ControlDimension = DEFAULT_RESULT_CARD_COLLAPSED_HEIGHT,
    body_height: ControlDimension = None,
    body_width: ControlDimension = DEFAULT_RESULT_BODY_WIDTH,
    expanded: bool = True,
) -> ft.Container:
    body_container = ft.Container(
        expand=_should_expand_body(expanded, height, body_height),
        visible=expanded,
        height=body_height,
        width=body_width,
        padding=12,
        bgcolor=BLUE_GREY,
        border_radius=6,
        content=_build_result_body(body_title, result),
    )
    toggle_button = _build_toggle_button(expanded)
    card = ft.Container(
        height=height if expanded else collapsed_height,
        width=width,
        padding=ft.Padding(left=18, top=14, right=18, bottom=16),
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=8,
        animate_size=240,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(
                            title,
                            expand=True,
                            size=17,
                            weight=ft.FontWeight.W_700,
                            color=TEXT_PRIMARY,
                        ),
                        _build_status_chip(status),
                        toggle_button,
                    ],
                ),
                body_container,
            ],
        ),
    )

    def on_toggle(_: ft.ControlEvent) -> None:
        next_expanded = not body_container.visible
        body_container.visible = next_expanded
        body_container.expand = _should_expand_body(
            next_expanded,
            height,
            body_height,
        )
        card.height = height if next_expanded else collapsed_height
        _sync_toggle_button(toggle_button, next_expanded)
        _update_if_mounted(toggle_button)
        _update_if_mounted(body_container)
        _update_if_mounted(card)

    toggle_button.on_click = on_toggle
    return card


def _build_result_body(
    body_title: str,
    result: Mapping[str, object],
) -> ft.Column:
    return ft.Column(
        spacing=4,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Text(
                body_title,
                size=11,
                weight=ft.FontWeight.W_700,
                color=PASTEL_DARK_PURPLE,
            ),
            ft.Text(
                _format_result(result),
                size=12,
                color=TEXT_SECONDARY,
                font_family="Consolas",
                selectable=True,
            ),
        ],
    )


def _build_status_chip(status: str) -> ft.Container:
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


def _build_toggle_button(expanded: bool) -> ft.IconButton:
    return ft.IconButton(
        icon=_toggle_icon(expanded),
        icon_size=22,
        icon_color=TEXT_SECONDARY,
        width=32,
        height=32,
        padding=0,
        tooltip=_toggle_tooltip(expanded),
    )


def _sync_toggle_button(button: ft.IconButton, expanded: bool) -> None:
    button.icon = _toggle_icon(expanded)
    button.tooltip = _toggle_tooltip(expanded)


def _toggle_icon(expanded: bool) -> ft.IconData:
    return (
        ft.Icons.KEYBOARD_ARROW_UP_ROUNDED
        if expanded
        else ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
    )


def _toggle_tooltip(expanded: bool) -> str:
    return "Recolher conteúdo" if expanded else "Mostrar conteúdo"


def _format_result(result: Mapping[str, object]) -> str:
    return json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def _should_expand_body(
    expanded: bool,
    height: ControlDimension,
    body_height: ControlDimension,
) -> bool:
    return expanded and height is not None and body_height is None


def _update_if_mounted(control: ft.Control) -> None:
    try:
        if control.page is not None:
            control.update()
    except RuntimeError:
        return
