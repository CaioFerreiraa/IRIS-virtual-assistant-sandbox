from __future__ import annotations

import textwrap
from dataclasses import replace

import flet as ft

from services.audio_device_service import AudioDeviceService
from services.speech_service import SpeechEvent, SpeechEventKind
from services.speech_service_manager import SpeechServiceManager
from services.voice_settings import VoiceSettings
from services.voice_settings_service import VoiceSettingsService
from ui.shared.components.audio_visualizer import AudioVisualizer
from ui.shared.components.toaster_handler import ToasterHandler
from ui.theme.colors import (
    BLUE_GREY,
    BORDER,
    PASTEL_BLUE,
    PASTEL_DARK_PURPLE,
    PASTEL_PURPLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


MODEL_OPTIONS = ("tiny", "base", "small", "medium", "large-v3", "turbo")
REALTIME_ONLY_FIELDS = {
    "realtime_model_size",
    "min_recording_duration",
    "realtime_processing_pause",
    "realtime_beam_size",
    "batch_size",
    "realtime_batch_size",
    "silero_sensitivity",
    "webrtc_sensitivity",
}
FIELD_HELP = {
    "enabled": "Liga ou desliga a captura de voz. O serviço permanece preparado enquanto a aplicação está aberta.",
    "mode": "Básico transcreve ao final da frase. Tempo real mostra texto e recomendações durante a fala.",
    "language": "Define o idioma esperado pelo Whisper. A detecção automática é mais flexível, mas pode ser mais lenta.",
    "model_size": "Modelo usado na transcrição final. Modelos maiores tendem a ser mais precisos e mais pesados.",
    "realtime_model_size": "Modelo leve usado nas atualizações parciais do RealtimeSTT.",
    "device": "Escolhe CPU, GPU NVIDIA com CUDA ou a seleção automática do dispositivo.",
    "compute_type": "Controla a precisão numérica. int8 economiza memória; float16 é indicado para GPUs compatíveis.",
    "input_device_index": "Seleciona uma entrada de áudio detectada pelo Windows ou usa o microfone padrão do sistema.",
    "sample_rate": "Quantidade de amostras capturadas por segundo. O Whisper é otimizado para 16.000 Hz.",
    "audio_threshold": "Volume mínimo para iniciar uma frase no modo básico. Aumente se ruídos acionarem a captura.",
    "silence_duration": "Tempo de silêncio necessário para considerar que a frase terminou.",
    "min_recording_duration": "Evita que o RealtimeSTT processe trechos de áudio curtos demais.",
    "realtime_processing_pause": "Intervalo entre atualizações parciais. Menor significa mais resposta e mais processamento.",
    "beam_size": "Quantidade de hipóteses comparadas na transcrição final. Valores maiores usam mais processamento.",
    "realtime_beam_size": "Quantidade de hipóteses comparadas nas transcrições parciais em tempo real.",
    "batch_size": "Tamanho do lote da transcrição final no RealtimeSTT. Zero mantém o comportamento padrão.",
    "realtime_batch_size": "Tamanho do lote das atualizações parciais. Zero mantém o comportamento padrão.",
    "vad_filter": "Remove trechos sem fala antes da transcrição para reduzir ruído e resultados vazios.",
    "silero_sensitivity": "Sensibilidade da detecção Silero usada pelo RealtimeSTT. Valores maiores detectam falas mais leves.",
    "webrtc_sensitivity": "Agressividade do detector WebRTC contra ruído, de 0 (leve) a 3 (agressiva).",
    "proper_names": "Nomes que o Whisper deve reconhecer com atenção especial. Separe-os por vírgulas.",
    "context": "Frases e assuntos adicionais que ajudam o Whisper a escolher palavras compatíveis com seu uso.",
    "hotwords": "Termos técnicos ou recorrentes que devem receber mais peso no reconhecimento.",
    "condition_on_previous_text": "Usa a transcrição anterior como contexto para manter coerência entre frases no modo básico.",
    "temperature": "Controla a variabilidade da transcrição. Zero produz resultados mais determinísticos.",
}
TOOLTIP_LINE_WIDTH = 52


class VoiceSettingsTab:
    def __init__(self, speech_manager: SpeechServiceManager, toaster_handler: ToasterHandler):
        self.speech_manager = speech_manager
        self.toaster_handler = toaster_handler
        self.settings_service = VoiceSettingsService(speech_manager)
        self.audio_device_service = AudioDeviceService()
        self.settings = self.settings_service.load()
        self.status_text = ft.Text("Voz desativada", size=13, color=TEXT_SECONDARY)
        self.test_microphone_button = ft.FilledButton(
            content=ft.Text("Testar microfone"),
            bgcolor=PASTEL_PURPLE,
            color=ft.Colors.WHITE,
            visible=False,
            on_click=self.on_test_microphone,
        )
        self.audio_visualizer = AudioVisualizer()
        self.status_card: ft.Container | None = None
        self.fields: dict[str, ft.Control] = {}
        self.field_wrappers: dict[str, ft.Container] = {}

    def build(self) -> ft.Column:
        self.field_wrappers = {}
        self.fields = self._build_fields()
        self.status_card = self._build_status_card()

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=24,
            controls=[
                self.status_card,
                self.audio_visualizer.build(),
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
                    "A palavra de ativação e os nomes de chamada dos módulos são aplicados internamente e não podem ser removidos.",
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
        microphone_options, microphone_helper = self._microphone_options(settings.input_device_index)
        return {
            "enabled": self._switch("Ativar comandos por voz", settings.enabled),
            "mode": self._dropdown(
                "Modo de reconhecimento",
                settings.mode,
                (("basic", "Básico - Faster-Whisper"), ("realtime", "Tempo real - RealtimeSTT + Faster-Whisper")),
                on_select=self.on_mode_change,
            ),
            "language": self._dropdown(
                "Idioma",
                settings.language,
                (("pt", "Português"), ("", "Detecção automática"), ("en", "Inglês"), ("es", "Espanhol")),
            ),
            "model_size": self._dropdown("Modelo final", settings.model_size, tuple((x, x) for x in MODEL_OPTIONS)),
            "realtime_model_size": self._dropdown(
                "Modelo em tempo real", settings.realtime_model_size, tuple((x, x) for x in MODEL_OPTIONS)
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
            "input_device_index": self._dropdown(
                "Microfone",
                "" if settings.input_device_index is None else str(settings.input_device_index),
                microphone_options,
                helper=microphone_helper,
            ),
            "sample_rate": self._text_field("Taxa de amostragem (Hz)", str(settings.sample_rate)),
            "audio_threshold": self._text_field("Limiar de áudio", str(settings.audio_threshold)),
            "silence_duration": self._text_field("Silêncio para encerrar a frase (s)", str(settings.silence_duration)),
            "min_recording_duration": self._text_field("Duração mínima da fala (s)", str(settings.min_recording_duration)),
            "realtime_processing_pause": self._text_field(
                "Intervalo das atualizações parciais (s)", str(settings.realtime_processing_pause)
            ),
            "beam_size": self._text_field("Beam size final", str(settings.beam_size)),
            "realtime_beam_size": self._text_field("Beam size em tempo real", str(settings.realtime_beam_size)),
            "batch_size": self._text_field("Batch size final", str(settings.batch_size)),
            "realtime_batch_size": self._text_field("Batch size em tempo real", str(settings.realtime_batch_size)),
            "vad_filter": self._switch("Ativar filtro de atividade de voz (VAD)", settings.vad_filter),
            "silero_sensitivity": self._text_field("Sensibilidade Silero (0 a 1)", str(settings.silero_sensitivity)),
            "webrtc_sensitivity": self._text_field("Agressividade WebRTC (0 a 3)", str(settings.webrtc_sensitivity)),
            "proper_names": self._text_field("Nomes próprios", settings.proper_names, multiline=True),
            "context": self._text_field("Contexto adicional", settings.context, multiline=True),
            "hotwords": self._text_field("Palavras importantes", settings.hotwords, multiline=True),
            "condition_on_previous_text": self._switch(
                "Usar o texto anterior como contexto no modo básico", settings.condition_on_previous_text
            ),
            "temperature": self._text_field("Temperatura (0 a 1)", str(settings.temperature)),
        }

    def _microphone_options(self, selected_index: int | None) -> tuple[tuple[tuple[str, str], ...], str]:
        options: list[tuple[str, str]] = [("", "Microfone padrão do sistema")]
        try:
            devices = self.audio_device_service.list_input_devices()
            options.extend((str(device.index), device.label) for device in devices)
            available_indexes = {device.index for device in devices}
            if selected_index is not None and selected_index not in available_indexes:
                options.append((str(selected_index), f"Microfone salvo não encontrado (entrada {selected_index})"))
            helper = f"{len(devices)} entrada(s) de áudio encontrada(s)."
        except RuntimeError as error:
            if selected_index is not None:
                options.append((str(selected_index), f"Microfone salvo (entrada {selected_index})"))
            helper = str(error)
        return tuple(options), helper

    def _build_status_card(self) -> ft.Container:
        return ft.Container(
            padding=ft.Padding(left=14, top=10, right=14, bottom=10),
            bgcolor=BLUE_GREY,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            content=ft.Row(
                spacing=9,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.MIC_NONE_ROUNDED, size=18, color=PASTEL_DARK_PURPLE),
                    ft.Container(expand=True, content=self.status_text),
                    self.test_microphone_button,
                ],
            ),
        )

    def _form_section(self, title: str, description: str, controls: list[ft.Control]) -> ft.Container:
        return ft.Container(
            padding=20,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            content=ft.Column(
                spacing=22,
                controls=[
                    ft.Column(
                        tight=True,
                        spacing=4,
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
        return ft.ResponsiveRow(
            spacing=18,
            run_spacing=24,
            controls=[self._build_field_wrapper(field_name) for field_name in field_names],
        )

    def _build_field_wrapper(self, field_name: str) -> ft.Container:
        wrapper = ft.Container(
            col={"sm": 12, "md": 6},
            visible=self._is_field_visible(field_name),
            content=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(expand=True, content=self.fields[field_name]),
                    ft.Container(
                        width=25,
                        height=25,
                        border_radius=20,
                        alignment=ft.Alignment.CENTER,
                        bgcolor=BLUE_GREY,
                        tooltip=ft.Tooltip(
                            message=self._build_tooltip_message(field_name),
                            bgcolor=BLUE_GREY,
                            text_style=ft.TextStyle(size=12, color=TEXT_PRIMARY),
                            padding=12,
                        ),
                        content=ft.Icon(
                            ft.Icons.INFO_OUTLINE_ROUNDED,
                            color=PASTEL_PURPLE,
                            size=15,
                        ),
                    ),
                ],
            ),
        )
        self.field_wrappers[field_name] = wrapper
        return wrapper

    def _build_tooltip_message(self, field_name: str) -> str:
        return textwrap.fill(FIELD_HELP[field_name], width=TOOLTIP_LINE_WIDTH)

    def _is_field_visible(self, field_name: str) -> bool:
        mode_field = self.fields.get("mode")
        mode = getattr(mode_field, "value", self.settings.mode)
        return mode == "realtime" or field_name not in REALTIME_ONLY_FIELDS

    def on_mode_change(self, event: ft.ControlEvent | None = None) -> None:
        for field_name, wrapper in self.field_wrappers.items():
            wrapper.visible = self._is_field_visible(field_name)
        if event is not None and self._is_mounted(event.control):
            event.control.page.update()

    def _switch(self, label: str, value: bool) -> ft.Container:
        switch = ft.Switch(value=value, active_color=PASTEL_DARK_PURPLE, active_track_color=PASTEL_PURPLE)
        return ft.Container(
            height=58,
            padding=ft.Padding(left=12, top=0, right=12, bottom=0),
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            alignment=ft.Alignment.CENTER_LEFT,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[ft.Text(label, size=13, color=TEXT_PRIMARY), switch],
            ),
            data=switch,
        )

    def _dropdown(
        self,
        label: str,
        value: str,
        options: tuple[tuple[str, str], ...],
        *,
        helper: str | None = None,
        on_select=None,
    ) -> ft.Dropdown:
        return ft.Dropdown(
            label=label,
            value=value,
            options=[ft.DropdownOption(key=key, text=text) for key, text in options],
            helper_text=helper,
            border_color=BORDER,
            focused_border_color=PASTEL_PURPLE,
            border_radius=8,
            dense=True,
            enable_search=True,
            on_select=on_select,
        )

    def _text_field(self, label: str, value: str, *, multiline: bool = False) -> ft.TextField:
        return ft.TextField(
            label=label,
            value=value,
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

    def on_test_microphone(self, event: ft.ControlEvent) -> None:
        event.page.go("/settings/voice_checking")

    def _read_form(self) -> VoiceSettings:
        value = lambda name: self._field_value(name)
        microphone_value = str(value("input_device_index") or "").strip()
        return replace(
            self.settings,
            enabled=bool(value("enabled")),
            mode=str(value("mode")),
            language=str(value("language") or ""),
            model_size=str(value("model_size")),
            realtime_model_size=str(value("realtime_model_size")),
            device=str(value("device")),
            compute_type=str(value("compute_type")),
            input_device_index=int(microphone_value) if microphone_value else None,
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
        if page is not None:
            page.run_task(self._apply_speech_event, event)

    async def _apply_speech_event(self, event: SpeechEvent) -> None:
        if event.kind == SpeechEventKind.AUDIO_LEVEL:
            self.audio_visualizer.set_level(event.audio_level)
            if self._is_mounted(self.audio_visualizer.root):
                self.audio_visualizer.root.update()
            return
        if event.kind == SpeechEventKind.TRANSCRIPTION:
            return

        if event.kind == SpeechEventKind.ERROR:
            self.status_text.value = event.message
            self.status_text.color = ft.Colors.RED_700
            self.test_microphone_button.visible = False
            self.audio_visualizer.set_level(0.0)
            self.toaster_handler.show_error(event.message, title="Voz indisponível")
        elif event.kind == SpeechEventKind.READY:
            self.status_text.value = "Serviço de voz pronto."
            self.status_text.color = PASTEL_DARK_PURPLE
            self.test_microphone_button.visible = True
            self.toaster_handler.show_success(event.message, title="Serviço de voz")
        elif event.kind == SpeechEventKind.STARTING:
            self.status_text.value = event.message
            self.status_text.color = TEXT_SECONDARY
            self.test_microphone_button.visible = False
        elif event.kind == SpeechEventKind.STOPPED:
            self.test_microphone_button.visible = False
            self.audio_visualizer.set_level(0.0)
            if not self.settings.enabled:
                self.status_text.value = "Voz desativada"
                self.status_text.color = TEXT_SECONDARY

        if self._is_mounted(self.status_text):
            self.status_card.update()
            if event.kind in {SpeechEventKind.ERROR, SpeechEventKind.STOPPED}:
                self.audio_visualizer.root.update()

    def sync_status_from_manager(self) -> None:
        if not self.settings.enabled:
            self.status_text.value = "Voz desativada"
            self.status_text.color = TEXT_SECONDARY
            self.test_microphone_button.visible = False
        elif self.speech_manager.backend_ready:
            self.status_text.value = "Serviço de voz pronto."
            self.status_text.color = PASTEL_DARK_PURPLE
            self.test_microphone_button.visible = True
        elif self.speech_manager.backend_error and self.speech_manager.last_event:
            self.status_text.value = self.speech_manager.last_event.message
            self.status_text.color = ft.Colors.RED_700
            self.test_microphone_button.visible = False
        else:
            self.status_text.value = "Preparando reconhecimento de voz..."
            self.status_text.color = TEXT_SECONDARY
            self.test_microphone_button.visible = False

        if self._is_mounted(self.status_text):
            self.status_card.update()

    def _is_mounted(self, control: ft.Control) -> bool:
        try:
            return control.page is not None
        except RuntimeError:
            return False
