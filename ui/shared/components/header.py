from collections.abc import Callable

import flet as ft

from services.speech_service import SpeechEvent, SpeechEventKind
from services.speech_service_manager import SpeechServiceManager
from ui.theme.colors import (
    BLUE_GREY,
    CANCEL,
    PASTEL_BLUE,
    PASTEL_DARK_PURPLE,
    PASTEL_GREEN,
    PASTEL_PURPLE,
    PASTEL_RED,
    PASTEL_YELLOW,
    SURFACE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.theme.fonts import TITLE_FONT


HEADER_HEIGHT = 74
WINDOW_BUTTON_WIDTH = 46
VOICE_ACTIVE_ROUTES = {"", "/", "/home", "/settings/voice_checking"}

NAV_ITEMS = (
    ("Início", "/home"),
    ("Comunidade", "/community"),
    ("Rotinas", "/routines"),
    ("Histórico", "/history"),
    ("Documentação", "/documentation"),
)


def build_header(
    current_route: str,
    on_navigate: Callable[[str], None],
    speech_manager: SpeechServiceManager | None = None,
) -> ft.Container:

    logo_section = ft.Container(
        height=HEADER_HEIGHT,
        padding=ft.Padding(left=20, top=8, right=10, bottom=8),
        alignment=ft.Alignment.CENTER_LEFT,
        content=ft.Row(
            spacing=5,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Image(src="assets/images/logo_transparent.png", width=60, height=60, fit=ft.BoxFit.CONTAIN),
                ft.Text("Iris", size=34, weight=ft.FontWeight.W_600, color=PASTEL_DARK_PURPLE, font_family=TITLE_FONT),
            ],
        ),
    )

    nav_section = ft.Row(
        height=HEADER_HEIGHT,
        spacing=8,
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.END,
        controls=[
            _nav_button( label=label, route=route, current_route=current_route, on_navigate=on_navigate)
            for label, route in NAV_ITEMS
        ],
    )

    window_section = ft.Row(
        spacing=15,
        alignment=ft.MainAxisAlignment.END,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            _build_voice_status(current_route, speech_manager),
            _build_user_button(current_route=current_route,on_navigate=on_navigate),
            ft.Container(
                height=42,
                margin=ft.Margin(right=8),
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.035,TEXT_PRIMARY),
                content=ft.Row(
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        build_window_button( icon_name=ft.Icons.REMOVE_ROUNDED, tooltip="Minimizar", on_click_action=minimize_window),
                        build_window_button( icon_name=ft.Icons.CROP_SQUARE_ROUNDED, tooltip="Maximizar", on_click_action=toggle_maximize),
                        build_window_button( icon_name=ft.Icons.CLOSE_ROUNDED, tooltip="Fechar", is_close_btn=True, on_click_action=close_window),
                    ],
                ),
            ),
        ],
    )

    return ft.Container(
        height=HEADER_HEIGHT,
        bgcolor=SURFACE,
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=12,
            color=ft.Colors.with_opacity(0.45, PASTEL_BLUE),
            offset=ft.Offset(0, 4),
        ),
        content=ft.Row(
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(expand=1, content=logo_section),
                ft.Container(expand=2, content=nav_section, height=HEADER_HEIGHT, alignment=ft.Alignment.BOTTOM_CENTER),
                ft.Container(expand=1, content=window_section, height=HEADER_HEIGHT, alignment=ft.Alignment.CENTER_RIGHT),
            ],
        ),
    )


class VoiceStatusIndicator:
    """Indicador visual do backend de voz e da disponibilidade por rota."""

    def __init__(self, current_route: str, speech_manager: SpeechServiceManager):
        self.current_route = current_route
        self.speech_manager = speech_manager
        self.is_voice_active = False
        self.icon = ft.Icon(ft.Icons.MIC_OFF_ROUNDED, size=21, color=PASTEL_DARK_PURPLE)
        self.container = ft.Container(
            width=42,
            height=42,
            border_radius=21,
            alignment=ft.Alignment.CENTER,
            content=self.icon,
            animate=ft.Animation(220, ft.AnimationCurve.EASE_OUT),
        )

    def build(self) -> ft.Container:
        self.speech_manager.subscribe(self.on_speech_event)
        self._sync_visual()
        return self.container

    def on_speech_event(self, event: SpeechEvent) -> None:
        if event.kind == SpeechEventKind.ACTIVATED:
            self.is_voice_active = True
        elif event.kind in {
            SpeechEventKind.DEACTIVATED,
            SpeechEventKind.ERROR,
            SpeechEventKind.STOPPED,
        }:
            self.is_voice_active = False
        elif event.kind not in {SpeechEventKind.READY, SpeechEventKind.STARTING}:
            return

        try:
            page = self.container.page
        except RuntimeError:
            return
        if page is not None:
            page.run_task(self._apply_speech_event)

    async def _apply_speech_event(self) -> None:
        self._sync_visual()
        try:
            if self.container.page is not None:
                self.container.update()
        except RuntimeError:
            return

    def _sync_visual(self) -> None:
        icon, background, tooltip = self._status_style()
        self.icon.icon = icon
        self.container.bgcolor = background
        self.container.tooltip = tooltip
        self.container.shadow = (
            ft.BoxShadow(
                spread_radius=3,
                blur_radius=18,
                color=ft.Colors.with_opacity(0.9, background),
                offset=ft.Offset(0, 0),
            )
            if self.is_voice_active
            else None
        )

    def _status_style(self):
        settings = self.speech_manager.current_settings
        is_voice_route = self.current_route in VOICE_ACTIVE_ROUTES
        if not is_voice_route:
            return (
                ft.Icons.MIC_OFF_ROUNDED,
                BLUE_GREY,
                "Comando de voz pausado. Use a rota Início ou o teste de microfone.",
            )
        if not settings.enabled:
            return (
                ft.Icons.MIC_OFF_ROUNDED,
                BLUE_GREY,
                "Comando de voz desativado nas configurações.",
            )
        if self.speech_manager.backend_error:
            message = self.speech_manager.last_event.message if self.speech_manager.last_event else ""
            return (
                ft.Icons.EMERGENCY_RECORDING_ROUNDED,
                PASTEL_RED,
                message or "O reconhecimento de voz encontrou um erro.",
            )
        if not self.speech_manager.backend_ready:
            return (
                ft.Icons.SETTINGS_VOICE_ROUNDED,
                PASTEL_YELLOW,
                "O reconhecimento de voz está carregando.",
            )
        if settings.mode == "realtime":
            return (
                ft.Icons.MIC_SHARP,
                PASTEL_GREEN,
                "Voz pronta no modo completo: RealtimeSTT + Faster-Whisper.",
            )
        return (
            ft.Icons.MIC_ROUNDED,
            PASTEL_BLUE,
            "Voz pronta no modo básico: Faster-Whisper.",
        )


def _build_voice_status(
    current_route: str,
    speech_manager: SpeechServiceManager | None,
) -> ft.Control:
    if speech_manager is None:
        return ft.Container(visible=False)
    return VoiceStatusIndicator(current_route, speech_manager).build()


def _nav_button(
    label: str,
    route: str,
    current_route: str,
    on_navigate: Callable[[str], None],
) -> ft.Container:
    is_active = current_route == route

    text_control = ft.Text(
        label,
        size=14,
        weight=(ft.FontWeight.W_600 if is_active else ft.FontWeight.W_500),
        color=(TEXT_PRIMARY if is_active else TEXT_SECONDARY),
    )

    def on_hover(e: ft.ControlEvent):
        hovering = bool(e.data)

        if not is_active:
            text_control.color = (TEXT_PRIMARY if hovering else TEXT_SECONDARY)

        e.control.bgcolor = (
            ft.Colors.with_opacity(0.04, PASTEL_PURPLE)
            if hovering
            else ft.Colors.TRANSPARENT
        )

        e.control.update()

    return ft.Container(
        height=HEADER_HEIGHT,
        padding=ft.Padding(left=8, top=0, right=8, bottom=0),
        alignment=ft.Alignment.BOTTOM_CENTER,
        bgcolor=ft.Colors.TRANSPARENT,
        on_click=lambda _: on_navigate(route),
        on_hover=on_hover,
        ink=True,
        ink_color=ft.Colors.with_opacity(0.08, PASTEL_PURPLE),
        content=ft.Container(
            height=50,
            padding=ft.Padding(left=2, top=0, right=2, bottom=12),
            alignment=ft.Alignment.BOTTOM_CENTER,
            border=ft.Border.only(
                bottom=ft.BorderSide(
                    width=3 if is_active else 0,
                    color=(
                        PASTEL_PURPLE
                        if is_active
                        else ft.Colors.TRANSPARENT
                    ),
                ),
            ),
            content=text_control,
        ),
    )


def _build_user_button(
    current_route: str,
    on_navigate: Callable[[str], None],
) -> ft.Container:
    is_active = current_route.startswith("/settings")

    icon_control = ft.Icon( icon=ft.Icons.SETTINGS_OUTLINED,size=21,color=PASTEL_DARK_PURPLE)

    def on_hover(e: ft.ControlEvent):
        hovering = bool(e.data)

        e.control.bgcolor = (
            PASTEL_PURPLE
            if hovering or is_active
            else ft.Colors.with_opacity(0.45, PASTEL_PURPLE)
        )

        e.control.update()

    return ft.Container(
        width=42,
        height=42,
        border_radius=21,
        alignment=ft.Alignment.CENTER,
        bgcolor=(
            PASTEL_PURPLE
            if is_active
            else ft.Colors.with_opacity(0.45, PASTEL_PURPLE)
        ),
        content=icon_control,
        on_click=lambda _: on_navigate("/settings"),
        on_hover=on_hover,
        tooltip="Usuário",
    )


def build_window_button(
    icon_name,
    tooltip: str,
    is_close_btn: bool = False,
    on_click_action=None,
) -> ft.Container:
    icon_control = ft.Icon(
        icon=icon_name,
        size=16,
        color=TEXT_PRIMARY,
    )

    def on_hover_button(e: ft.ControlEvent):
        hovering = bool(e.data)

        if hovering:
            e.control.bgcolor = (
                CANCEL
                if is_close_btn
                else ft.Colors.with_opacity(0.08, TEXT_PRIMARY)
            )

            icon_control.color = (
                ft.Colors.WHITE
                if is_close_btn
                else PASTEL_DARK_PURPLE
            )
        else:
            e.control.bgcolor = ft.Colors.TRANSPARENT
            icon_control.color = TEXT_PRIMARY

        e.control.update()

    return ft.Container(
        width=WINDOW_BUTTON_WIDTH,
        height=42,
        alignment=ft.Alignment.CENTER,
        bgcolor=ft.Colors.TRANSPARENT,
        border_radius=8,
        tooltip=tooltip,
        content=icon_control,
        on_click=on_click_action,
        on_hover=on_hover_button,
    )


def minimize_window(e: ft.ControlEvent):
    e.page.window.minimized = True
    e.page.update()


def toggle_maximize(e: ft.ControlEvent):
    e.page.window.maximized = not e.page.window.maximized
    e.page.update()


async def close_window(e: ft.ControlEvent):
    await e.page.window.close()
