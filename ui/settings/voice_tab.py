from __future__ import annotations

from dataclasses import replace

import flet as ft

from services.speech_service import SpeechEvent, SpeechEventKind
from services.speech_service_manager import SpeechServiceManager
from services.voice_settings import VoiceSettings
from services.voice_settings_service import VoiceSettingsService
from ui.shared.components.toaster_handler import ToasterHandler
from ui.theme.colors import (
    BORDER,
    PASTEL_DARK_PURPLE,
    PASTEL_PURPLE,
    BLUE_GREY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


MODEL_OPTIONS = ("tiny", "base", "small", "medium", "large-v3", "turbo")


class VoiceSettingsTab:
    def __init__(self, speech_manager: SpeechServiceManager, toaster_handler: ToasterHandler):
        self.speech_manager = speech_manager
        self.toaster_handler = toaster_handler
        self.settings_service = VoiceSettingsService(speech_manager)
        self.settings = self.settings_service.load()
        self.status_text = ft.Text("Voz desativada", size=13, color=TEXT_SECONDARY)
        self.fields: dict[str, ft.Control] = {}

    def build(self) -> ft.Column:
        self.fields = self._build_fields()

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=18,
            controls=[
                self._build_status_card(),
                self._form_section(
                    "Ativação e desempenho",
                    "O modo básico transcreve depois da frase. O modo em tempo real atualiza a recomendação enquanto você fala.",
                    [
                        self._field_grid("enabled", "mode", "language", "model_size"),
                        self._field_grid("realtime_model_size", "device", "compute_type", "input_device_index"),
                    ],
                ),
                self._form_section(
                    "Captura e detecção de fala",
                    "Ajuste estes valores somente se houver cortes, ruído ou atraso excessivo.",
                    [
                        self._field_grid("sample_rate", "audio_threshold", "silence_duration", "min_recording_duration"),
                        self._field_grid("realtime_processing_pause", "vad_filter", "silero_sensitivity", "webrtc_sensitivity"),
                    ],
                ),
                self._form_section(
                    "Reconhecimento",
                    "A palavra de ativação e seu contexto são aplicados internamente e não podem ser removidos.",
                    [
                        self._field_grid("beam_size", "realtime_beam_size", "batch_size", "realtime_batch_size"),
                        self._field_grid("temperature", "condition_on_previous_text", "proper_names", "context", "hotwords"),
                    ],
                ),
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.FilledButton(
                            content=ft.Text("Salvar"),
                            bgcolor=PASTEL_PURPLE,
                            color=ft.Colors.WHITE,
                            on_click=self.on_save,
                        )
                    ],
                ),
            ],
        )

    def _build_fields(self) -> dict[str, ft.Control]:
        settings = self.settings
        return {
            "enabled": self._switch("Ativar comandos por voz", settings.enabled),
            "mode": self._dropdown(
                "Modo de reconhecimento",
                settings.mode,
                (("basic", "Básico - Faster-Whisper"), ("realtime", "Tempo real - RealtimeSTT + Faster-Whisper")),
            ),
            "language": self._dropdown(
                "Idioma",
                settings.language,
                (("pt", "Português"), ("", "Detecção automática"), ("en", "Inglês"), ("es", "Espanhol")),
            ),
            "model_size": self._dropdown("Modelo final", settings.model_size, tuple((x, x) for x in MODEL_OPTIONS)),
            "realtime_model_size": self._dropdown(
                "Modelo em tempo real",
                settings.realtime_model_size,
                tuple((x, x) for x in MODEL_OPTIONS),
            ),
            "device": self._dropdown(
                "Processamento",
                settings.device,
                (("cpu", "CPU"), ("cuda", "GPU NVIDIA (CUDA)"), ("auto", "Automático")),
            ),
            "compute_type": self._dropdown(
                "Precisão",
                settings.compute_type,
                (("int8", "int8 - leve"), ("float16", "float16"), ("float32", "float32"), ("default", "Padrão do dispositivo")),
            ),
            "input_device_index": self._text_field(
                "Índice do microfone",
                "" if settings.input_device_index is None else str(settings.input_device_index),
                helper="Deixe vazio para usar o microfone padrão do Windows.",
            ),
            "sample_rate": self._text_field("Taxa de amostragem (Hz)", str(settings.sample_rate)),
            "audio_threshold": self._text_field(
                "Limiar de áudio",
                str(settings.audio_threshold),
                helper="Usado no modo básico. Padrão: 0,025.",
            ),
            "silence_duration": self._text_field("Silêncio para encerrar a frase (s)", str(settings.silence_duration)),
            "min_recording_duration": self._text_field("Duração mínima da fala (s)", str(settings.min_recording_duration)),
            "realtime_processing_pause": self._text_field(
                "Intervalo das atualizações parciais (s)",
                str(settings.realtime_processing_pause),
                helper="Valores menores respondem mais rápido e usam mais processamento.",
            ),
            "beam_size": self._text_field("Beam size final", str(settings.beam_size)),
            "realtime_beam_size": self._text_field("Beam size em tempo real", str(settings.realtime_beam_size)),
            "batch_size": self._text_field(
                "Batch size final",
                str(settings.batch_size),
                helper="Use 0 para desativar o processamento em lote.",
            ),
            "realtime_batch_size": self._text_field("Batch size em tempo real", str(settings.realtime_batch_size)),
            "vad_filter": self._switch("Ativar filtro de atividade de voz (VAD)", settings.vad_filter),
            "silero_sensitivity": self._text_field("Sensibilidade Silero (0 a 1)", str(settings.silero_sensitivity)),
            "webrtc_sensitivity": self._text_field("Agressividade WebRTC (0 a 3)", str(settings.webrtc_sensitivity)),
            "proper_names": self._text_field(
                "Nomes próprios",
                settings.proper_names,
                helper="Separe nomes por vírgulas para melhorar o reconhecimento.",
                multiline=True,
            ),
            "context": self._text_field(
                "Contexto adicional",
                settings.context,
                helper="Exemplo: comandos de aplicativos, arquivos e agenda.",
                multiline=True,
            ),
            "hotwords": self._text_field(
                "Palavras importantes",
                settings.hotwords,
                helper="Termos técnicos ou palavras que devem receber mais atenção.",
                multiline=True,
            ),
            "condition_on_previous_text": self._switch(
                "Usar o texto anterior como contexto no modo básico",
                settings.condition_on_previous_text,
            ),
            "temperature": self._text_field("Temperatura (0 a 1)", str(settings.temperature)),
        }

    def _build_status_card(self) -> ft.Container:
        return ft.Container(
            padding=ft.Padding(left=14, top=10, right=14, bottom=10),
            bgcolor=BLUE_GREY,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            content=ft.Row(
                spacing=9,
                controls=[
                    ft.Icon(ft.Icons.MIC_NONE_ROUNDED, size=18, color=PASTEL_DARK_PURPLE),
                    self.status_text,
                ],
            ),
        )

    def _form_section(self, title: str, description: str, controls: list[ft.Control]) -> ft.Container:
        return ft.Container(
            padding=18,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Column(
                        tight=True,
                        spacing=3,
                        controls=[
                            ft.Text(title, size=17, weight=ft.FontWeight.W_700, color=TEXT_PRIMARY),
                            ft.Text(description, size=13, color=TEXT_SECONDARY),
                        ],
                    ),
                    *controls,
                ],
            ),
        )

    def _field_grid(self, *field_names: str) -> ft.ResponsiveRow:
        controls = []
        for field_name in field_names:
            field = self.fields[field_name]
            field.col = {"sm": 12, "md": 6}
            controls.append(field)
        return ft.ResponsiveRow(spacing=12, run_spacing=12, controls=controls)

    def _switch(self, label: str, value: bool) -> ft.Container:
        switch = ft.Switch(
            value=value,
            active_color=PASTEL_DARK_PURPLE,
            active_track_color=PASTEL_PURPLE,
        )
        return ft.Container(
            height=58,
            padding=ft.Padding(left=12, top=0, right=12, bottom=0),
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            alignment=ft.Alignment.CENTER_LEFT,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text(label, size=13, color=TEXT_PRIMARY),
                    switch,
                ],
            ),
            data=switch,
        )

    def _dropdown(self, label: str, value: str, options: tuple[tuple[str, str], ...]) -> ft.Dropdown:
        return ft.Dropdown(
            label=label,
            value=value,
            options=[ft.DropdownOption(key=key, text=text) for key, text in options],
            border_color=BORDER,
            focused_border_color=PASTEL_PURPLE,
            border_radius=8,
            dense=True,
        )

    def _text_field(
        self,
        label: str,
        value: str,
        *,
        helper: str | None = None,
        multiline: bool = False,
    ) -> ft.TextField:
        return ft.TextField(
            label=label,
            value=value,
            helper=helper,
            multiline=multiline,
            min_lines=2 if multiline else None,
            max_lines=3 if multiline else 1,
            border_color=BORDER,
            focused_border_color=PASTEL_PURPLE,
            border_radius=8,
            dense=not multiline,
        )

    def on_save(self, event=None) -> None:
        try:
            values = self._read_form()
            self.settings = self.settings_service.save(values)
        except Exception as error:
            self.toaster_handler.show_error(str(error), title="Erro ao salvar voz")
            return

        message = (
            "Configurações salvas. O serviço de voz está sendo preparado."
            if self.settings.enabled
            else "Configurações salvas. O serviço de voz foi desativado."
        )
        self.toaster_handler.show_success(message, title="Configuração de voz")
        self.sync_status_from_manager()

    def _read_form(self) -> VoiceSettings:
        value = lambda name: self._field_value(name)
        microphone_text = str(value("input_device_index") or "").strip()
        return replace(
            self.settings,
            enabled=bool(value("enabled")),
            mode=str(value("mode")),
            language=str(value("language") or ""),
            model_size=str(value("model_size")),
            realtime_model_size=str(value("realtime_model_size")),
            device=str(value("device")),
            compute_type=str(value("compute_type")),
            input_device_index=int(microphone_text) if microphone_text else None,
            sample_rate=int(str(value("sample_rate")).strip()),
            audio_threshold=self._float_value("audio_threshold"),
            silence_duration=self._float_value("silence_duration"),
            min_recording_duration=self._float_value("min_recording_duration"),
            realtime_processing_pause=self._float_value("realtime_processing_pause"),
            beam_size=int(str(value("beam_size")).strip()),
            realtime_beam_size=int(str(value("realtime_beam_size")).strip()),
            batch_size=int(str(value("batch_size")).strip()),
            realtime_batch_size=int(str(value("realtime_batch_size")).strip()),
            vad_filter=bool(value("vad_filter")),
            silero_sensitivity=self._float_value("silero_sensitivity"),
            webrtc_sensitivity=int(str(value("webrtc_sensitivity")).strip()),
            proper_names=str(value("proper_names") or "").strip(),
            context=str(value("context") or "").strip(),
            hotwords=str(value("hotwords") or "").strip(),
            condition_on_previous_text=bool(value("condition_on_previous_text")),
            temperature=self._float_value("temperature"),
        ).validate()

    def _field_value(self, field_name: str):
        field = self.fields[field_name]
        if isinstance(field, ft.Container) and isinstance(field.data, ft.Switch):
            return field.data.value
        return getattr(field, "value", None)

    def _float_value(self, field_name: str) -> float:
        raw_value = str(self._field_value(field_name) or "").strip().replace(",", ".")
        return float(raw_value)

    def on_speech_event(self, event: SpeechEvent) -> None:
        try:
            page = self.status_text.page
        except RuntimeError:
            return
        if page is None:
            return
        page.run_task(self._apply_speech_event, event)

    async def _apply_speech_event(self, event: SpeechEvent) -> None:
        if event.kind == SpeechEventKind.ERROR:
            self.status_text.value = event.message
            self.status_text.color = ft.Colors.RED_700
            self.toaster_handler.show_error(event.message, title="Voz indisponível")
        elif event.kind == SpeechEventKind.READY:
            self.status_text.value = event.message
            self.status_text.color = PASTEL_DARK_PURPLE
            self.toaster_handler.show_success(event.message, title="Serviço de voz")
        elif event.kind == SpeechEventKind.STARTING:
            self.status_text.value = event.message
            self.status_text.color = TEXT_SECONDARY
        elif event.kind == SpeechEventKind.STOPPED and not self.settings.enabled:
            self.status_text.value = "Voz desativada"
            self.status_text.color = TEXT_SECONDARY

        if self._is_mounted(self.status_text):
            self.status_text.update()

    def sync_status_from_manager(self) -> None:
        if not self.settings.enabled:
            self.status_text.value = "Voz desativada"
            self.status_text.color = TEXT_SECONDARY
        elif self.speech_manager.last_event and self.speech_manager.last_event.kind == SpeechEventKind.READY:
            self.status_text.value = self.speech_manager.last_event.message
            self.status_text.color = PASTEL_DARK_PURPLE
        elif self.speech_manager.last_event and self.speech_manager.last_event.kind == SpeechEventKind.ERROR:
            self.status_text.value = self.speech_manager.last_event.message
            self.status_text.color = ft.Colors.RED_700
        else:
            self.status_text.value = "Preparando reconhecimento de voz..."
            self.status_text.color = TEXT_SECONDARY

        if self._is_mounted(self.status_text):
            self.status_text.update()

    def _is_mounted(self, control: ft.Control) -> bool:
        try:
            return control.page is not None
        except RuntimeError:
            return False
