from __future__ import annotations

from collections.abc import Callable
import textwrap

import flet as ft

from ui.theme.colors import (
    BLUE_GREY,
    BORDER,
    GREY_200,
    PASTEL_DARK_PURPLE,
    PASTEL_PURPLE,
    SURFACE,
    TEXT_PRIMARY, GREY_100,
)
from ui.shared.components.tooltip_container import build_tooltip_container


ControlCallback = Callable[[ft.ControlEvent], None]
FLOATING_SAVE_BAR_ANIMATION_DURATION = 180
FLOATING_SAVE_BAR_BOTTOM = 8
FLOATING_SAVE_BAR_HIDDEN_BOTTOM = -72
INPUT_TEXT_SIZE = 14


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
        bgcolor=GREY_100 if disabled else None,
        color=TEXT_PRIMARY if disabled else None,
        text_style=ft.TextStyle(
            size=INPUT_TEXT_SIZE,
            color=TEXT_PRIMARY if disabled else None,
        ),
        label_style=ft.TextStyle(
            size=INPUT_TEXT_SIZE,
            color=TEXT_PRIMARY if disabled else None,
        ),
        hint_style=ft.TextStyle(
            size=INPUT_TEXT_SIZE,
            color=TEXT_PRIMARY if disabled else None,
        ),
        helper_style=ft.TextStyle(color=TEXT_PRIMARY) if disabled else None,
        border_color=TEXT_PRIMARY if disabled else BORDER,
        focused_border_color=TEXT_PRIMARY if disabled else PASTEL_PURPLE,
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
        helper=helper,
        disabled=disabled,
        expand=expand,
        bgcolor=GREY_100 if disabled else None,
        focused_bgcolor=GREY_100 if disabled else None,
        text_style=ft.TextStyle(
            size=INPUT_TEXT_SIZE,
            color=TEXT_PRIMARY if disabled else None,
        ),
        label_style=ft.TextStyle(
            size=INPUT_TEXT_SIZE,
            color=TEXT_PRIMARY if disabled else None,
        ),
        hint_style=ft.TextStyle(
            size=INPUT_TEXT_SIZE,
            color=TEXT_PRIMARY if disabled else None,
        ),
        helper_style=ft.TextStyle(color=TEXT_PRIMARY) if disabled else None,
        cursor_color=TEXT_PRIMARY if disabled else None,
        border_color=TEXT_PRIMARY if disabled else BORDER,
        focused_border_color=TEXT_PRIMARY if disabled else PASTEL_PURPLE,
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


def build_secondary_button(
    label: str,
    on_click: ControlCallback | None,
    *,
    disabled: bool = False,
    expand: bool = False,
    visible: bool = True,
    tooltip: str | None = None,
) -> ft.FilledButton:
    return ft.FilledButton(
        content=ft.Text(label),
        tooltip=build_tooltip_container(tooltip) if tooltip else None,
        bgcolor=BLUE_GREY,
        color=TEXT_PRIMARY,
        disabled=disabled,
        expand=expand,
        visible=visible,
        on_click=on_click,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=5),
        ),
    )


class FloatingSaveBar(ft.Container):
    def __init__(
        self,
        label: str,
        on_click: ControlCallback | None,
        *,
        disabled: bool = False,
        visible: bool = True,
    ) -> None:
        self.is_visible = visible
        self.panel = ft.Container(
            opacity=1 if visible else 0,
            animate_opacity=FLOATING_SAVE_BAR_ANIMATION_DURATION,
            padding=8,
            bgcolor=ft.Colors.with_opacity(0.50, SURFACE),
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
        )
        super().__init__(
            left=0,
            right=0,
            bottom=(
                FLOATING_SAVE_BAR_BOTTOM
                if visible
                else FLOATING_SAVE_BAR_HIDDEN_BOTTOM
            ),
            alignment=ft.Alignment.CENTER,
            animate_position=FLOATING_SAVE_BAR_ANIMATION_DURATION,
            visible=True,
            ignore_interactions=not visible,
            content=self.panel,
        )

    def set_visible(self, visible: bool) -> None:
        if self.is_visible == visible:
            return
        self.is_visible = visible
        self.ignore_interactions = not visible
        self.panel.opacity = 1 if visible else 0
        self.bottom = (
            FLOATING_SAVE_BAR_BOTTOM
            if visible
            else FLOATING_SAVE_BAR_HIDDEN_BOTTOM
        )

    def update_visibility(self, visible: bool) -> None:
        self.set_visible(visible)
        _update_if_mounted(self)


def build_floating_save_bar(
    label: str,
    on_click: ControlCallback | None,
    *,
    disabled: bool = False,
    visible: bool = True,
) -> FloatingSaveBar:
    return FloatingSaveBar(
        label,
        on_click,
        disabled=disabled,
        visible=visible,
    )


def _update_if_mounted(control: ft.Control) -> None:
    try:
        if control.page is not None:
            control.update()
    except RuntimeError:
        return
