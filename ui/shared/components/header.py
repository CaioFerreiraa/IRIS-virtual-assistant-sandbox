from collections.abc import Callable

import flet as ft

from services.speech_service import SpeechEvent, SpeechEventKind
from services.speech_service_manager import SpeechServiceManager
from ui.shared.components.custom_dialog import custom_dialog
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
VOICE_STATUS_DIALOG_WIDTH = 520

NAV_ITEMS = (
    ("Início", "/home"),
    ("Comunidade", "/community"),
    ("Rotinas", "/routines"),
    ("Histórico", "/history"),
    ("Documentação", "/documentation"),
)

VOICE_STATUS_STYLES = {
    "no_microphone": (
        ft.Icons.MIC_OFF_ROUNDED,
        BLUE_GREY,
        "Nenhum microfone conectado.",
    ),
    "paused_route": (
        ft.Icons.MIC_OFF_ROUNDED,
        BLUE_GREY,
        "Comando de voz pausado. Use a rota Início ou o teste de microfone.",
    ),
    "disabled": (
        ft.Icons.MIC_OFF_ROUNDED,
        BLUE_GREY,
        "Comando de voz desativado nas configurações.",
    ),
    "loading": (
        ft.Icons.SETTINGS_VOICE_ROUNDED,
        PASTEL_YELLOW,
        "O reconhecimento de voz está carregando.",
    ),
    "error": (
        ft.Icons.MIC_OFF_SHARP,
        PASTEL_RED,
        "O reconhecimento de voz encontrou um erro.",
    ),
    "ready_basic": (
        ft.Icons.MIC_ROUNDED,
        PASTEL_BLUE,
        "Voz pronta no modo básico: Faster-Whisper.",
    ),
    "ready_realtime": (
        ft.Icons.MIC_SHARP,
        PASTEL_GREEN,
        "Voz pronta no modo completo: RealtimeSTT + Faster-Whisper.",
    ),
    "unavailable": (
        ft.Icons.MIC_NONE_ROUNDED,
        BLUE_GREY,
        "Serviço de voz indisponível nesta execução.",
    ),
}

VOICE_STATUS_ORDER = (
    "no_microphone",
    "paused_route",
    "disabled",
    "unavailable",
    "loading",
    "error",
    "ready_basic",
    "ready_realtime",
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

    def __init__(
        self,
        current_route: str,
        speech_manager: SpeechServiceManager,
        microphone_available: bool,
    ):
        self.current_route = current_route
        self.speech_manager = speech_manager
        self.microphone_available = microphone_available
        self.is_voice_active = False
        self.icon = ft.Icon(ft.Icons.MIC_OFF_ROUNDED, size=21, color=PASTEL_DARK_PURPLE)
        self.container = ft.Container(
            width=42,
            height=42,
            border_radius=21,
            alignment=ft.Alignment.CENTER,
            content=self.icon,
            on_click=lambda event: _show_voice_status_dialog_from_indicator(self, event),
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
        status_key = _voice_status_key(
            current_route=self.current_route,
            speech_manager=self.speech_manager,
            is_voice_active=self.is_voice_active,
            microphone_available=self.microphone_available,
        )
        icon, background, tooltip = VOICE_STATUS_STYLES[status_key]

        if status_key == "error":
            message = self.speech_manager.last_event.message if self.speech_manager.last_event else ""
            tooltip = message or tooltip

        return icon, background, tooltip


def _open_voice_status_dialog(
    page: ft.Page,
    active_key: str,
    active_message: str,
) -> None:
    dialog = custom_dialog(
        title="Status do microfone",
        content=_build_voice_status_dialog_content(active_key, active_message),
        width=VOICE_STATUS_DIALOG_WIDTH,
        icon=ft.Icons.MIC_ROUNDED,
        accent_color=BLUE_GREY,
        alignment=ft.Alignment.CENTER,
        inset_padding=ft.Padding(left=24, top=24, right=24, bottom=24),
    )
    page.overlay.append(dialog)
    dialog.open = True
    page.update()


def _show_voice_status_dialog_from_indicator(
    indicator: VoiceStatusIndicator,
    event: ft.ControlEvent,
) -> None:
    page = getattr(event, "page", None)
    if page is None:
        return

    _open_voice_status_dialog(
        page=page,
        active_key=_voice_status_key(
            current_route=indicator.current_route,
            speech_manager=indicator.speech_manager,
            is_voice_active=indicator.is_voice_active,
            microphone_available=indicator.microphone_available,
        ),
        active_message=indicator._status_style()[2],
    )


def _voice_status_key(
    current_route: str,
    speech_manager: SpeechServiceManager,
    is_voice_active: bool,
    microphone_available: bool,
) -> str:
    if not microphone_available:
        return "no_microphone"
    if current_route not in VOICE_ACTIVE_ROUTES:
        return "paused_route"

    settings = speech_manager.current_settings
    if not settings.enabled:
        return "disabled"
    if speech_manager.backend_error:
        return "error"
    if not speech_manager.backend_ready:
        return "loading"
    if settings.mode == "realtime":
        return "ready_realtime"
    return "ready_basic"


def _build_voice_status(
    current_route: str,
    speech_manager: SpeechServiceManager | None,
) -> ft.Control:
    if speech_manager is None:
        return _build_unavailable_voice_status()
    microphone_available = speech_manager.microphone_available is not False
    return VoiceStatusIndicator(
        current_route,
        speech_manager,
        microphone_available=microphone_available,
    ).build()


def _build_unavailable_voice_status() -> ft.Container:
    icon, background, tooltip = VOICE_STATUS_STYLES["unavailable"]

    def on_click(event: ft.ControlEvent) -> None:
        page = getattr(event, "page", None)
        if page is None:
            return
        _open_voice_status_dialog(
            page=page,
            active_key="unavailable",
            active_message=tooltip,
        )

    return ft.Container(
        width=42,
        height=42,
        border_radius=21,
        alignment=ft.Alignment.CENTER,
        bgcolor=background,
        content=ft.Icon(icon, size=21, color=PASTEL_DARK_PURPLE),
        on_click=on_click,
        tooltip=tooltip,
    )


def _build_voice_status_dialog_content(
    active_key: str,
    active_message: str,
) -> ft.Container:
    return ft.Container(
        width=VOICE_STATUS_DIALOG_WIDTH,
        content=ft.Column(
            tight=True,
            spacing=12,
            controls=[
                ft.Text(
                    f"Status atual: {active_message}",
                    size=14,
                    color=TEXT_PRIMARY,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Column(
                    tight=True,
                    spacing=8,
                    controls=[
                        _build_voice_status_row(status_key, active_key)
                        for status_key in VOICE_STATUS_ORDER
                    ],
                ),
            ],
        ),
    )


def _build_voice_status_row(status_key: str, active_key: str) -> ft.Container:
    icon, background, message = VOICE_STATUS_STYLES[status_key]
    is_active = status_key == active_key
    return ft.Container(
        padding=ft.Padding(left=10, top=8, right=10, bottom=8),
        border_radius=7,
        bgcolor=ft.Colors.with_opacity(0.45, background) if is_active else ft.Colors.TRANSPARENT,
        border=ft.Border.all(1, background),
        content=ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=32,
                    height=32,
                    border_radius=16,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=background,
                    content=ft.Icon(icon, size=18, color=PASTEL_DARK_PURPLE),
                ),
                ft.Text(
                    message,
                    size=13,
                    color=TEXT_PRIMARY if is_active else TEXT_SECONDARY,
                    expand=True,
                ),
            ],
        ),
    )


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
