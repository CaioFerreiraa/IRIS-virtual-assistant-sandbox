import time

import flet as ft

from ui.shared.components.custom_dialog import show_custom_dialog
from ui.theme.colors import (
    BORDER,
    CANCEL,
    CONFIRM,
    PASTEL_DARK_PURPLE,
    PASTEL_PURPLE,
    SURFACE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)

class ToasterHandler:
    def __init__(self, page: ft.Page):
        self.page = page
        self._toast = self._build_toast_container()
        self._toast_dialog = self._build_toast_dialog()
        self._toast_id = 0
        self._is_mounted = False
        self._is_hovered = False
        self._current_title = ""
        self._current_message = ""
        self._current_kind = "info"

    def mount(self) -> None:
        if self._is_mounted:
            return

        self.page.overlay.append(self._toast_dialog)
        self._is_mounted = True

    def show_success(self, message: str, title: str = "Sucesso") -> None:
        self.show(title=title, message=message, kind="success")

    def show_error(self, message: str, title: str = "Erro") -> None:
        self.show(title=title, message=message, kind="error")

    def show_warning(self, message: str, title: str = "Atenção") -> None:
        self.show(title=title, message=message, kind="warning")

    def show_info(self, message: str, title: str = "IRIS") -> None:
        self.show(title=title, message=message, kind="info")

    def show(
        self,
        title: str,
        message: str,
        kind: str = "info",
        duration_seconds: float = 4,
    ) -> None:
        self.mount()
        self._toast_id += 1
        toast_id = self._toast_id
        self._current_title = title
        self._current_message = message
        self._current_kind = kind

        self._toast.content = _build_toast_content(title, message, kind)
        self._toast.opacity = 1
        self._toast_dialog.open = True
        self._update(page_layout_changed=True)

        self.page.run_thread(self._schedule_hide, toast_id, duration_seconds)

    def hide(self) -> None:
        self._toast.opacity = 0
        self._toast_dialog.open = False
        self._update(page_layout_changed=True)

    def _schedule_hide(self, toast_id: int, duration_seconds: float) -> None:
        elapsed_seconds = 0.0
        tick_seconds = 0.1

        while elapsed_seconds < duration_seconds:
            time.sleep(tick_seconds)

            if toast_id != self._toast_id:
                return

            if self._is_hovered:
                continue

            elapsed_seconds += tick_seconds

        self.hide()

    def _on_hover(self, event) -> None:
        self._is_hovered = str(event.data).lower() == "true"

    def _open_modal(self, event=None) -> None:
        if not self._current_title and not self._current_message:
            return

        show_custom_dialog(
            page=self.page,
            title=self._current_title,
            message=self._current_message,
            kind=self._current_kind,
        )

    def _update(self, *, page_layout_changed: bool = False) -> None:
        try:
            if page_layout_changed or not self.page.controls:
                self.page.update()
            else:
                self._toast.update()
        except RuntimeError:
            return

    def _build_toast_container(self) -> ft.Container:
        return ft.Container(
            width=437,
            opacity=0,
            content=_build_toast_content("IRIS", "-", "info"),
            on_hover=self._on_hover,
            on_click=self._open_modal,
            ink=True,
            ink_color=PASTEL_PURPLE,
            animate_opacity=180,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=31,
                color="#22000000",
                offset=ft.Offset(0, 13),
            ),
        )

    def _build_toast_dialog(self) -> ft.AlertDialog:
        return ft.AlertDialog(
            modal=False,
            alignment=ft.Alignment.BOTTOM_RIGHT,
            inset_padding=ft.Padding(left=24, top=24, right=27, bottom=50),
            bgcolor=ft.Colors.TRANSPARENT,
            barrier_color=ft.Colors.TRANSPARENT,
            elevation=0,
            content_padding=0,
            title_padding=0,
            actions_padding=0,
            shape=ft.RoundedRectangleBorder(radius=7),
            content=self._toast,
        )


def _build_toast_content(title: str, message: str, kind: str) -> ft.Container:
    accent_color = _accent_color(kind)
    icon = _icon(kind)

    return ft.Container(
        height=116,
        bgcolor=SURFACE,
        border=ft.Border.all(1, PASTEL_PURPLE),
        border_radius=7,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Row(
            spacing=0,
            controls=[
                ft.Container(
                    width=7,
                    height=116,
                    bgcolor=PASTEL_DARK_PURPLE,
                ),
                ft.Container(
                    expand=True,
                    padding=ft.Padding(left=20, top=18, right=20, bottom=18),
                    content=ft.Column(
                        tight=True,
                        spacing=4,
                        controls=[
                            ft.Row(
                                spacing=9,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        width=24,
                                        height=24,
                                        border_radius=6,
                                        alignment=ft.Alignment.CENTER,
                                        bgcolor=accent_color,
                                        border=ft.Border.all(1, BORDER),
                                        content=ft.Icon(
                                            icon=icon,
                                            size=14,
                                            color=PASTEL_DARK_PURPLE,
                                        ),
                                    ),
                                    ft.Text(
                                        title,
                                        size=16,
                                        weight=ft.FontWeight.W_700,
                                        color=TEXT_PRIMARY,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                        no_wrap=True,
                                        tooltip=title,
                                        expand=True,
                                    ),
                                ],
                            ),
                            ft.Text(
                                message or "-",
                                size=15,
                                color=TEXT_SECONDARY,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                tooltip=message or "-",
                                expand=True,
                            ),
                        ],
                    ),
                ),
            ],
        ),
    )


def _accent_color(kind: str) -> str:
    return {
        "success": CONFIRM,
        "error": CANCEL,
        "warning": WARNING,
    }.get(kind, PASTEL_PURPLE)




def _icon(kind: str):
    return {
        "success": ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
        "error": ft.Icons.ERROR_OUTLINE_ROUNDED,
        "warning": ft.Icons.WARNING_AMBER_ROUNDED,
    }.get(kind, ft.Icons.INFO_OUTLINE_ROUNDED)
