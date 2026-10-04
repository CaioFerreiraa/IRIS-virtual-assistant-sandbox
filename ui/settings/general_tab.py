from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import flet as ft

from services.general_settings_service import GeneralSettingsService
from ui.shared.components.toaster_handler import ToasterHandler
from ui.theme.colors import (
    BORDER,
    BLUE_GREY,
    PASTEL_DARK_PURPLE,
    PASTEL_PURPLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


def build_general_settings_tab(
    settings_service: GeneralSettingsService,
    toaster_handler: ToasterHandler,
    on_background_execution_change: Callable[[bool], bool],
    on_listening_overlay_change: Callable[[bool], bool],
    on_notification_mode_change: Callable[[str], bool],
    get_notification_status: Callable[[], str | None],
) -> ft.Container:
    settings = settings_service.load()
    background_switch = ft.Switch(
        value=settings.background_execution_enabled,
        active_color=PASTEL_DARK_PURPLE,
        active_track_color=PASTEL_PURPLE,
    )

    def on_background_change(event: ft.ControlEvent) -> None:
        nonlocal settings
        enabled = bool(event.control.value)
        try:
            settings = settings_service.save(
                replace(settings, background_execution_enabled=enabled)
            )
            available = on_background_execution_change(enabled)
        except Exception as error:
            event.control.value = settings.background_execution_enabled
            event.control.update()
            toaster_handler.show_error(
                str(error),
                title="Erro ao salvar configurações",
            )
            return

        if enabled and not available:
            toaster_handler.show_warning(
                "A preferência foi salva, mas a bandeja não está disponível neste ambiente.",
                title="Execução em segundo plano",
            )
            return

        if settings.notification_mode == "windows":
            update_notification_status()

        message = (
            "A IRIS continuará ativa na bandeja ao fechar a janela."
            if enabled
            else "Fechar a janela encerrará a IRIS."
        )
        toaster_handler.show_success(message, title="Configurações gerais")

    background_switch.on_change = on_background_change

    overlay_switch = ft.Switch(
        value=settings.listening_overlay_enabled,
        active_color=PASTEL_DARK_PURPLE,
        active_track_color=PASTEL_PURPLE,
    )

    def on_overlay_change(event: ft.ControlEvent) -> None:
        nonlocal settings
        enabled = bool(event.control.value)
        try:
            settings = settings_service.save(
                replace(settings, listening_overlay_enabled=enabled)
            )
            available = on_listening_overlay_change(enabled)
        except Exception as error:
            event.control.value = settings.listening_overlay_enabled
            event.control.update()
            toaster_handler.show_error(
                str(error),
                title="Erro ao salvar configurações",
            )
            return

        if enabled and not available:
            toaster_handler.show_warning(
                "O indicador flutuante está disponível somente no Windows.",
                title="Indicador de voz",
            )
            return

        message = (
            "O indicador aparecerá quando a IRIS reconhecer a palavra de ativação."
            if enabled
            else "O indicador flutuante foi desativado."
        )
        toaster_handler.show_success(message, title="Configurações gerais")

    overlay_switch.on_change = on_overlay_change

    notification_dropdown = ft.Dropdown(
        value=settings.notification_mode,
        options=[
            ft.DropdownOption(key="none", text="Sem Notify"),
            ft.DropdownOption(key="iris", text="Notify da IRIS"),
            ft.DropdownOption(key="windows", text="Notificação do Windows"),
        ],
        width=420,
        border_color=BORDER,
        focused_border_color=PASTEL_PURPLE,
        color=TEXT_PRIMARY,
    )
    notification_status_text = ft.Text(size=12, color=TEXT_SECONDARY, visible=False)

    def update_notification_status() -> None:
        status = get_notification_status() if settings.notification_mode == "windows" else None
        notification_status_text.value = status or ""
        notification_status_text.visible = bool(status)
        try:
            notification_status_text.update()
        except RuntimeError:
            pass

    def on_notification_change(event: ft.ControlEvent) -> None:
        nonlocal settings
        mode = str(event.control.value or "iris")
        try:
            saved = settings_service.save(replace(settings, notification_mode=mode))
            available = on_notification_mode_change(mode)
            settings = saved
            update_notification_status()
        except Exception as error:
            event.control.value = settings.notification_mode
            event.control.update()
            toaster_handler.show_error(str(error), title="Erro ao salvar configurações")
            return
        if mode == "windows" and not available:
            toaster_handler.show_warning(
                get_notification_status() or "Notificações do Windows indisponíveis.",
                title="Notificações do Windows",
            )
        else:
            toaster_handler.show_success(
                "Canal de notificações atualizado.", title="Configurações gerais"
            )

    notification_dropdown.on_select = on_notification_change
    update_notification_status()

    return ft.Container(
        padding=24,
        bgcolor=BLUE_GREY,
        border=ft.Border.all(1, BORDER),
        border_radius=8,
        content=ft.Column(
            tight=True,
            spacing=18,
            controls=[
                ft.Column(
                    tight=True,
                    spacing=6,
                    controls=[
                        ft.Text(
                            "Configurações gerais",
                            size=18,
                            weight=ft.FontWeight.W_700,
                            color=TEXT_PRIMARY,
                        ),
                        ft.Text(
                            "Defina o comportamento geral da aplicação.",
                            size=14,
                            color=TEXT_SECONDARY,
                        ),
                    ],
                ),
                ft.Container(
                    height=72,
                    padding=ft.Padding(left=12, top=0, right=12, bottom=0),
                    border=ft.Border.all(1, BORDER),
                    border_radius=8,
                    alignment=ft.Alignment.CENTER_LEFT,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(
                                expand=True,
                                tight=True,
                                spacing=3,
                                controls=[
                                    ft.Text(
                                        "Manter a IRIS em segundo plano",
                                        size=13,
                                        color=TEXT_PRIMARY,
                                    ),
                                    ft.Text(
                                        "Ao fechar a janela, mantém a aplicação disponível na bandeja do Windows.",
                                        size=12,
                                        color=TEXT_SECONDARY,
                                    ),
                                ],
                            ),
                            background_switch,
                        ],
                    ),
                    data=background_switch,
                ),
                ft.Container(
                    height=72,
                    padding=ft.Padding(left=12, top=0, right=12, bottom=0),
                    border=ft.Border.all(1, BORDER),
                    border_radius=8,
                    alignment=ft.Alignment.CENTER_LEFT,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(
                                expand=True,
                                tight=True,
                                spacing=3,
                                controls=[
                                    ft.Text(
                                        "Mostrar indicador flutuante de voz",
                                        size=13,
                                        color=TEXT_PRIMARY,
                                    ),
                                    ft.Text(
                                        "Exibe o texto reconhecido sem interromper o aplicativo em uso.",
                                        size=12,
                                        color=TEXT_SECONDARY,
                                    ),
                                ],
                            ),
                            overlay_switch,
                        ],
                    ),
                    data=overlay_switch,
                ),
                ft.Container(
                    padding=ft.Padding(left=12, top=10, right=12, bottom=12),
                    border=ft.Border.all(1, BORDER),
                    border_radius=8,
                    content=ft.Column(
                        tight=True,
                        spacing=8,
                        controls=[
                            ft.Text("Notificações em segundo plano", size=13, color=TEXT_PRIMARY),
                            ft.Text(
                                "Escolha um único canal para avisos fora da janela da IRIS.",
                                size=12,
                                color=TEXT_SECONDARY,
                            ),
                            notification_dropdown,
                            notification_status_text,
                        ],
                    ),
                ),
            ],
        ),
    )
