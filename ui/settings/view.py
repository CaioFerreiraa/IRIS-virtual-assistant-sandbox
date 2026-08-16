from __future__ import annotations

import flet as ft

from services.speech_service_manager import SpeechServiceManager
from ui.settings.general_tab import build_general_settings_tab
from ui.settings.passwords_tab import build_passwords_tab
from ui.settings.voice_tab import VoiceSettingsTab
from ui.shared.components.route_content_container import build_route_content_container
from ui.shared.components.toaster_handler import ToasterHandler
from ui.theme.colors import (
    BORDER,
    PASTEL_PURPLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


SETTINGS_TABS = (
    ("general", "Configurações gerais", ft.Icons.TUNE_ROUNDED),
    ("voice", "Configuração de voz", ft.Icons.MIC_ROUNDED),
    ("passwords", "Senhas", ft.Icons.LOCK_OUTLINE_ROUNDED),
)


def build_settings_view(
    speech_manager: SpeechServiceManager,
    toaster_handler: ToasterHandler,
) -> ft.Container:
    return SettingsViewState(speech_manager, toaster_handler).build()


class SettingsViewState:
    def __init__(self, speech_manager: SpeechServiceManager, toaster_handler: ToasterHandler):
        self.speech_manager = speech_manager
        self.voice_tab = VoiceSettingsTab(speech_manager, toaster_handler)
        self.active_tab = "voice"
        self.tab_content = ft.Container(expand=True)
        self.tab_buttons: dict[str, ft.Container] = {}

    def build(self) -> ft.Container:
        for key, label, icon in SETTINGS_TABS:
            self.tab_buttons[key] = self._build_tab_button(key, label, icon)

        self._render_tab()
        self.speech_manager.subscribe(self.voice_tab.on_speech_event)
        self.voice_tab.sync_status_from_manager()

        return build_route_content_container(
            icon=ft.Icons.SETTINGS_ROUNDED,
            title="Configurações",
            subtitle="Personalize o comportamento da IRIS.",
            content=ft.Column(
                expand=True,
                spacing=20,
                controls=[
                    ft.Container(
                        border=ft.Border.only(bottom=ft.BorderSide(1, BORDER)),
                        content=ft.Row(spacing=20, controls=list(self.tab_buttons.values())),
                    ),
                    self.tab_content,
                ],
            ),
        )

    def _build_tab_button(self, key: str, label: str, icon) -> ft.Container:
        is_active = key == self.active_tab
        icon_control = ft.Icon(icon, size=18, color=TEXT_PRIMARY if is_active else TEXT_SECONDARY)
        text_control = ft.Text(
            label,
            size=14,
            weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_500,
            color=TEXT_PRIMARY if is_active else TEXT_SECONDARY,
        )
        indicator = ft.Container(
            height=50,
            padding=ft.Padding(left=4, top=0, right=4, bottom=12),
            alignment=ft.Alignment.BOTTOM_CENTER,
            border=ft.Border.only(
                bottom=ft.BorderSide(width=3 if is_active else 0, color=PASTEL_PURPLE if is_active else ft.Colors.TRANSPARENT),
            ),
            content=ft.Row(
                tight=True,
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[icon_control, text_control],
            ),
        )

        def on_hover(event: ft.ControlEvent):
            hovering = bool(event.data)
            if key != self.active_tab:
                color = TEXT_PRIMARY if hovering else TEXT_SECONDARY
                icon_control.color = color
                text_control.color = color
            event.control.bgcolor = (
                ft.Colors.with_opacity(0.04, PASTEL_PURPLE)
                if hovering
                else ft.Colors.TRANSPARENT
            )
            event.control.update()

        return ft.Container(
            height=50,
            padding=ft.Padding(left=12, top=0, right=12, bottom=0),
            alignment=ft.Alignment.BOTTOM_CENTER,
            bgcolor=ft.Colors.TRANSPARENT,
            on_click=lambda _, selected=key: self.on_select_tab(selected),
            on_hover=on_hover,
            ink=True,
            ink_color=ft.Colors.with_opacity(0.08, PASTEL_PURPLE),
            content=indicator,
        )

    def on_select_tab(self, key: str) -> None:
        self.active_tab = key
        self._render_tab()
        if self._is_mounted(self.tab_content):
            self.tab_content.update()
            for button in self.tab_buttons.values():
                button.update()

    def _render_tab(self) -> None:
        self._sync_tab_buttons()

        if self.active_tab == "voice":
            # Origem: ui.settings.voice_tab.VoiceSettingsTab.build
            self.tab_content.content = self.voice_tab.build()
        elif self.active_tab == "general":
            # Origem: ui.settings.general_tab.build_general_settings_tab
            self.tab_content.content = build_general_settings_tab()
        else:
            # Origem: ui.settings.passwords_tab.build_passwords_tab
            self.tab_content.content = build_passwords_tab()

    def _sync_tab_buttons(self) -> None:
        for key, button in self.tab_buttons.items():
            is_active = key == self.active_tab
            indicator = button.content
            tab_row = indicator.content
            icon_control, text_control = tab_row.controls

            indicator.border = ft.Border.only(
                bottom=ft.BorderSide(width=3 if is_active else 0, color=PASTEL_PURPLE if is_active else ft.Colors.TRANSPARENT),
            )
            icon_control.color = TEXT_PRIMARY if is_active else TEXT_SECONDARY
            text_control.color = TEXT_PRIMARY if is_active else TEXT_SECONDARY
            text_control.weight = ft.FontWeight.W_600 if is_active else ft.FontWeight.W_500

    def _is_mounted(self, control: ft.Control) -> bool:
        try:
            return control.page is not None
        except RuntimeError:
            return False
