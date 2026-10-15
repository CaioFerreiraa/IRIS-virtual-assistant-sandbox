from collections.abc import Callable, Sequence

import flet as ft

from ui.theme.colors import (
    BLUE_GREY,
    PASTEL_DARK_PURPLE,
    SURFACE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


DialogCallback = Callable[[ft.ControlEvent], None]
MIN_DIALOG_CONTENT_WIDTH = 320
MIN_DIALOG_CONTENT_HEIGHT = 120
DEFAULT_RESIZED_CONTENT_HEIGHT = 240


def custom_dialog(
    title: str,
    message: str | None = None,
    *,
    kind: str = "info",
    content: ft.Control | None = None,
    actions: Sequence[ft.Control] | None = None,
    close_text: str = "Fechar",
    on_close: DialogCallback | None = None,
    on_dismiss: DialogCallback | None = None,
    modal: bool = False,
    width: int = 460,
    alignment=ft.Alignment.TOP_CENTER,
    inset_padding: ft.Padding | None = None,
    icon=None,
    icon_bgcolor: str | None = None,
    selectable_message: bool = True,
) -> ft.AlertDialog:
    effective_icon = icon or _icon(kind)
    dialog_actions = list(actions) if actions is not None else [_default_close_button(close_text)]
    dialog_content = content or _message_content(message, width, selectable_message)
    resize_handle = _build_resize_handle(dialog_content, width)
    close_button = _build_close_button()

    dialog = ft.AlertDialog(
        modal=modal,
        alignment=alignment,
        inset_padding=inset_padding or ft.Padding(left=24, top=200, right=24, bottom=24),
        bgcolor=SURFACE,
        title_padding=ft.Padding(left=22, top=20, right=22, bottom=0),
        content_padding=ft.Padding(left=22, top=14, right=22, bottom=10),
        actions_padding=ft.Padding(left=16, top=0, right=16, bottom=14),
        shape=ft.RoundedRectangleBorder(radius=7),
        title=ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=32,
                    height=32,
                    border_radius=8,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=icon_bgcolor or BLUE_GREY,
                    content=ft.Icon(
                        icon=effective_icon,
                        size=18,
                        color=PASTEL_DARK_PURPLE,
                    ),
                ),
                ft.Text(
                    title,
                    size=18,
                    weight=ft.FontWeight.W_700,
                    color=TEXT_PRIMARY,
                    expand=True,
                ),
                resize_handle,
                close_button,
            ],
        ),
        content=dialog_content,
        actions=dialog_actions,
        actions_alignment=ft.MainAxisAlignment.END,
        on_dismiss=on_dismiss,
    )

    close_button.on_click = _build_close_handler(dialog, on_close)
    if actions is None:
        dialog_actions[0].on_click = _build_close_handler(dialog, on_close)

    return dialog


def show_custom_dialog(
    page: ft.Page,
    title: str,
    message: str | None = None,
    **dialog_options,
) -> ft.AlertDialog:
    dialog = custom_dialog(title=title, message=message, **dialog_options)
    page.overlay.append(dialog)
    dialog.open = True
    page.update()
    return dialog


def _message_content(
    message: str | None,
    width: int,
    selectable: bool,
) -> ft.Container:
    return ft.Container(
        width=width,
        padding=ft.Padding(top=20, bottom=20, right=10, left=10),
        content=ft.Column(
            tight=True,
            spacing=0,
            controls=[
                ft.Text(
                    message or "-",
                    size=15,
                    color=TEXT_SECONDARY,
                    selectable=selectable,
                ),
            ],
        ),
    )


def _default_close_button(close_text: str) -> ft.TextButton:
    return ft.TextButton(
        content=close_text,
        style=ft.ButtonStyle(color=PASTEL_DARK_PURPLE),
    )


def _build_close_button() -> ft.IconButton:
    return ft.IconButton(
        icon=ft.Icons.CLOSE_ROUNDED,
        icon_size=20,
        icon_color=TEXT_SECONDARY,
        width=32,
        height=32,
        padding=0,
        tooltip="Fechar diálogo",
    )


def _build_resize_handle(content: ft.Control, default_width: int) -> ft.GestureDetector:
    """Cria a alça que redimensiona o conteúdo de qualquer diálogo compartilhado."""
    initial_width = _dimension_or_default(getattr(content, "width", None), default_width)
    initial_height = _dimension_or_default(getattr(content, "height", None), None)

    def on_resize(event: ft.DragUpdateEvent) -> None:
        delta = event.local_delta
        if delta is None:
            return

        if delta.x:
            current_width = _dimension_or_default(
                getattr(content, "width", None), initial_width,
            )
            content.width = max(MIN_DIALOG_CONTENT_WIDTH, current_width + delta.x)
        if delta.y:
            current_height = _dimension_or_default(
                getattr(content, "height", None),
                initial_height or DEFAULT_RESIZED_CONTENT_HEIGHT,
            )
            content.height = max(MIN_DIALOG_CONTENT_HEIGHT, current_height + delta.y)
        _update_if_mounted(content)

    return ft.GestureDetector(
        width=28,
        height=32,
        mouse_cursor=ft.MouseCursor.RESIZE_UP_LEFT_DOWN_RIGHT,
        tooltip="Arraste para redimensionar o diálogo",
        on_pan_update=on_resize,
        content=ft.Container(
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(
                ft.Icons.DRAG_HANDLE_ROUNDED,
                size=18,
                color=TEXT_SECONDARY,
            ),
        ),
    )


def _build_close_handler(
    dialog: ft.AlertDialog,
    on_close: DialogCallback | None,
) -> DialogCallback:
    def close_dialog(event: ft.ControlEvent) -> None:
        dialog.open = False

        if on_close is not None:
            on_close(event)

        page = getattr(event, "page", None)
        if page is not None:
            page.update()
            return

        try:
            dialog.update()
        except RuntimeError:
            return

    return close_dialog


def _dimension_or_default(
    value: int | float | None,
    default: int | float | None,
) -> float | None:
    return float(value) if value is not None else default


def _update_if_mounted(control: ft.Control) -> None:
    try:
        if control.page is not None:
            control.update()
    except RuntimeError:
        return


def _icon(kind: str):
    return {
        "success": ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
        "error": ft.Icons.ERROR_OUTLINE_ROUNDED,
        "warning": ft.Icons.WARNING_AMBER_ROUNDED,
    }.get(kind, ft.Icons.INFO_OUTLINE_ROUNDED)
