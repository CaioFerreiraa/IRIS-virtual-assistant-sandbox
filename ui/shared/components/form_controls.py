from __future__ import annotations

from collections.abc import Callable
import textwrap

import flet as ft

from ui.theme.colors import BORDER, PASTEL_DARK_PURPLE, PASTEL_PURPLE, SURFACE
from ui.shared.components.tooltip_container import build_tooltip_container


ControlCallback = Callable[[ft.ControlEvent], None]


def build_dropdown(
    label: str,
    value: str,
    options: tuple[tuple[str, str], ...],
    *,
    helper: str | None = None,
    disabled: bool = False,
    expand: bool = True,
    on_select: ControlCallback | None = None,
    width: int | None = None,
    height: int | None = None,
    menu_width: int | None = None,
    menu_height: int | None = None,
    on_focus: ControlCallback | None = None,
) -> ft.Dropdown:
    return ft.Dropdown(
        label=label,
        value=value,
        options=[ft.DropdownOption(key=key, text=text) for key, text in options],
        helper_text=helper,
        tooltip=build_tooltip_container(helper) if helper else None,
        disabled=disabled,
        expand=expand,
        border_color=BORDER,
        focused_border_color=PASTEL_PURPLE,
        border_radius=8,
        dense=True,
        enable_search=True,
        width=width,
        height=height,
        menu_width=menu_width,
        menu_height=menu_height,
        on_select=on_select,
        on_focus=on_focus,
    )


def build_text_field(
    label: str,
    value: str,
    *,
    helper: str | None = None,
    multiline: bool = False,
    disabled: bool = False,
    expand: bool = True,
) -> ft.TextField:
    return ft.TextField(
        label=label,
        value=value,
        multiline=multiline,
        min_lines=2 if multiline else None,
        max_lines=3 if multiline else 1,
        tooltip=build_tooltip_container(helper) if helper else None,
        disabled=disabled,
        expand=expand,
        border_color=BORDER,
        focused_border_color=PASTEL_PURPLE,
        border_radius=8,
        dense=not multiline,
    )


def build_tooltip_message(message: str, *, width: int = 52) -> str:
    return textwrap.fill(message, width=width)


def build_primary_button(
    label: str,
    on_click: ControlCallback | None,
    *,
    disabled: bool = False,
    expand: bool = False,
    visible: bool = True,
) -> ft.FilledButton:
    return ft.FilledButton(
        content=ft.Text(label),
        bgcolor=PASTEL_DARK_PURPLE,
        color=ft.Colors.WHITE,
        disabled=disabled,
        expand=expand,
        visible=visible,
        on_click=on_click,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=5),
        ),
    )


def build_floating_save_bar(
    label: str,
    on_click: ControlCallback | None,
    *,
    disabled: bool = False,
    visible: bool = True,
) -> ft.Container:
    return ft.Container(
        align=ft.Alignment.BOTTOM_CENTER,
        margin=ft.Margin(left=0, top=0, right=0, bottom=8),
        visible=visible,
        content=ft.Container(
            padding=8,
            bgcolor=SURFACE,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            shadow=ft.BoxShadow(
                blur_radius=14,
                color=ft.Colors.with_opacity(0.14, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
            content=build_primary_button(
                label,
                on_click,
                disabled=disabled,
            ),
        ),
    )
