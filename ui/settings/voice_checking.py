from __future__ import annotations

import flet as ft

from services.speech_service import SpeechEvent, SpeechEventKind
from services.speech_service_manager import SpeechServiceManager
from ui.shared.components.audio_visualizer import AudioVisualizer
from ui.shared.components.route_content_container import build_route_content_container
from ui.shared.components.toaster_handler import ToasterHandler
from ui.theme.colors import (
    APP_BACKGROUND,
    BLUE_GREY,
    BORDER,
    PASTEL_DARK_PURPLE,
    PASTEL_PURPLE,
    SURFACE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


def build_voice_checking_view(
    speech_manager: SpeechServiceManager,
    toaster_handler: ToasterHandler,
) -> ft.Container:
    return VoiceCheckingView(speech_manager, toaster_handler).build()


class VoiceCheckingView:
    """Modal de diagnóstico que apresenta transcrições sem exigir a palavra IRIS."""

    def __init__(self, speech_manager: SpeechServiceManager, toaster_handler: ToasterHandler):
        self.speech_manager = speech_manager
        self.toaster_handler = toaster_handler
        self.settings = speech_manager.current_settings
        self.audio_visualizer = AudioVisualizer("Sinal recebido do microfone")
        self.status_icon = ft.Icon(ft.Icons.SETTINGS_VOICE_ROUNDED, color=PASTEL_DARK_PURPLE, size=20)
        self.status_text = ft.Text(size=13, color=TEXT_SECONDARY)
        self.realtime_text = ft.Text(
            "Aguardando você falar...",
            size=15,
            color=TEXT_SECONDARY,
            selectable=True,
        )
        self.final_results = ft.ListView(
            height=150,
            spacing=8,
            auto_scroll=True,
            controls=[ft.Text("Aguardando você concluir uma frase...", size=14, color=TEXT_SECONDARY)],
        )
        self.status_card: ft.Container | None = None
        self.has_final_results = False
        self.last_final_text = ""

    def build(self) -> ft.Container:
        self._sync_status()
        self.speech_manager.subscribe(self.on_speech_event)

        transcription_panels: list[ft.Control] = []
        if self.settings.mode == "realtime":
            transcription_panels.append(
                self._build_transcription_panel(
                    "RealtimeSTT · texto parcial",
                    "Atualiza enquanto você fala.",
                    ft.Container(height=150, content=self.realtime_text),
                    col={"sm": 12, "md": 6},
                )
            )
        transcription_panels.append(
            self._build_transcription_panel(
                "Faster-Whisper · resultado final",
                "Aparece quando a frase é concluída pelo silêncio.",
                self.final_results,
                col={"sm": 12, "md": 6 if self.settings.mode == "realtime" else 12},
            )
        )

        self.status_card = self._build_status_card()
        modal = ft.Container(
            width=930,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=28,
                color=ft.Colors.with_opacity(0.18, TEXT_PRIMARY),
                offset=ft.Offset(0, 8),
            ),
            content=build_route_content_container(
                icon=ft.Icons.MIC_ROUNDED,
                title="Teste do reconhecimento de voz",
                subtitle=(
                    "Fale normalmente. Nesta tela não é necessário dizer “IRIS”; "
                    "toda transcrição reconhecida será exibida abaixo."
                ),
                expand=False,
                content=ft.Column(
                    tight=True,
                    spacing=20,
                    controls=[
                        self.status_card,
                        self.audio_visualizer.build(),
                        ft.ResponsiveRow(
                            spacing=16,
                            run_spacing=16,
                            controls=transcription_panels,
                        ),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.FilledButton(
                                    content=ft.Text("Voltar"),
                                    bgcolor=PASTEL_DARK_PURPLE,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=5),
                                    ),
                                    color=ft.Colors.WHITE,
                                    on_click=self.on_back,
                                )
                            ],
                        ),
                    ],
                ),
            ),
        )

        return ft.Container(
            expand=True,
            bgcolor=ft.Colors.with_opacity(0.45, APP_BACKGROUND),
            alignment=ft.Alignment.CENTER,
            padding=28,
            content=modal,
        )

    def _build_status_card(self) -> ft.Container:
        return ft.Container(
            padding=ft.Padding(left=14, top=11, right=14, bottom=11),
            bgcolor=BLUE_GREY,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            content=ft.Row(spacing=9, controls=[self.status_icon, self.status_text]),
        )

    def _build_transcription_panel(
        self,
        title: str,
        description: str,
        content: ft.Control,
        *,
        col: dict[str, int],
    ) -> ft.Container:
        return ft.Container(
            col=col,
            padding=16,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            bgcolor=BLUE_GREY,
            content=ft.Column(
                tight=True,
                spacing=9,
                controls=[
                    ft.Text(title, size=15, weight=ft.FontWeight.W_700, color=TEXT_PRIMARY),
                    ft.Text(description, size=12, color=TEXT_SECONDARY),
                    ft.Divider(height=1, color=BORDER),
                    content,
                ],
            ),
        )

    def on_speech_event(self, event: SpeechEvent) -> None:
        try:
            page = self.status_text.page
        except RuntimeError:
            return
        if page is not None:
            page.run_task(self._apply_speech_event, event)

    async def _apply_speech_event(self, event: SpeechEvent) -> None:
        if event.kind == SpeechEventKind.AUDIO_LEVEL:
            self.audio_visualizer.set_level(event.audio_level)
            self._update_if_mounted(self.audio_visualizer.root)
            return

        if event.kind == SpeechEventKind.TRANSCRIPTION:
            if event.source == "realtime_stt":
                self.realtime_text.value = event.text
                self.realtime_text.color = TEXT_PRIMARY
                self._update_if_mounted(self.realtime_text)
            elif event.source == "faster_whisper" and event.text != self.last_final_text:
                self.last_final_text = event.text
                if not self.has_final_results:
                    self.final_results.controls.clear()
                    self.has_final_results = True
                self.final_results.controls.append(
                    ft.Container(
                        padding=ft.Padding(left=10, top=8, right=10, bottom=8),
                        bgcolor=SURFACE,
                        border_radius=7,
                        content=ft.Text(event.text, size=14, color=TEXT_PRIMARY, selectable=True),
                    )
                )
                if len(self.final_results.controls) > 20:
                    self.final_results.controls.pop(0)
                self._update_if_mounted(self.final_results)
            return

        if event.kind == SpeechEventKind.READY:
            self.status_icon.icon = ft.Icons.MIC_ROUNDED
            self.status_text.value = self._ready_message()
            self.status_text.color = PASTEL_DARK_PURPLE
        elif event.kind == SpeechEventKind.STARTING:
            self.status_icon.icon = ft.Icons.SETTINGS_VOICE_ROUNDED
            self.status_text.value = event.message
            self.status_text.color = TEXT_SECONDARY
        elif event.kind == SpeechEventKind.ERROR:
            self.status_icon.icon = ft.Icons.EMERGENCY_RECORDING_ROUNDED
            self.status_text.value = event.message
            self.status_text.color = ft.Colors.RED_700
            self.audio_visualizer.set_level(0.0)
            self._update_if_mounted(self.audio_visualizer.root)
            self.toaster_handler.show_error(event.message, title="Teste de voz indisponível")
        elif event.kind == SpeechEventKind.STOPPED:
            self.audio_visualizer.set_level(0.0)
            self._update_if_mounted(self.audio_visualizer.root)

        self._update_if_mounted(self.status_card)

    def _sync_status(self) -> None:
        if not self.settings.enabled:
            self.status_icon.icon = ft.Icons.MIC_OFF_ROUNDED
            self.status_text.value = "O reconhecimento de voz está desativado nas configurações."
        elif self.speech_manager.backend_error and self.speech_manager.last_event:
            self.status_icon.icon = ft.Icons.EMERGENCY_RECORDING_ROUNDED
            self.status_text.value = self.speech_manager.last_event.message
            self.status_text.color = ft.Colors.RED_700
        elif self.speech_manager.backend_ready:
            self.status_icon.icon = ft.Icons.MIC_ROUNDED
            self.status_text.value = self._ready_message()
            self.status_text.color = PASTEL_DARK_PURPLE
        else:
            self.status_icon.icon = ft.Icons.SETTINGS_VOICE_ROUNDED
            self.status_text.value = "Preparando reconhecimento de voz..."

    def _ready_message(self) -> str:
        if self.settings.mode == "realtime":
            return "Microfone pronto no modo completo. Fale para comparar as duas transcrições."
        return "Microfone pronto no modo básico. Fale e aguarde o fim da frase."

    def on_back(self, event: ft.ControlEvent) -> None:
        event.page.go("/settings")

    def _update_if_mounted(self, control: ft.Control | None) -> None:
        if control is None:
            return
        try:
            control.update()
        except RuntimeError:
            return
