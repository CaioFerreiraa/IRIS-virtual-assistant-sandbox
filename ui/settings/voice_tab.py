from __future__ import annotations

import asyncio
import logging
from dataclasses import replace

import flet as ft
from services.audio_device_service import AudioDeviceService, Microphone, MicrophoneLevelMonitor
from services.speech_service import SpeechEvent, SpeechEventKind
from services.speech_service_manager import SpeechServiceManager
from services.voice_settings import VoiceSettings
from services.voice_settings_service import VoiceSettingsService
from ui.shared.components.audio_visualizer import AudioVisualizer
from ui.shared.components.form_controls import (
    build_dropdown,
    build_primary_button,
    build_text_field,
    build_tooltip_message,
)
from ui.shared.components.toaster_handler import ToasterHandler
from ui.theme.colors import (
    BLUE_GREY,
    BORDER,
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
    "input_device_index": "Seleciona um microfone disponível no Windows. Sem seleção, a IRIS usa o padrão do sistema.",
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
MICROPHONE_DROPDOWN_MENU_WIDTH = 420
MICROPHONE_DROPDOWN_MENU_HEIGHT = 220
DEFAULT_MICROPHONE_ID = ""


class VoiceSettingsContent(ft.Column):
    def __init__(self, on_mount, on_unmount, **kwargs):
        super().__init__(**kwargs)
        self._on_mount = on_mount
        self._on_unmount = on_unmount

    def did_mount(self) -> None:
        self._on_mount()

    def will_unmount(self) -> None:
        self._on_unmount()


class VoiceSettingsTab:
    def __init__(self, speech_manager: SpeechServiceManager, toaster_handler: ToasterHandler):
        self.speech_manager = speech_manager
        self.toaster_handler = toaster_handler
        self.settings_service = VoiceSettingsService(speech_manager)
        self.settings = self.settings_service.load()
        self.status_text = ft.Text("Voz desativada", size=13, color=TEXT_SECONDARY)
        self.selected_microphone_text = ft.Text(
            "Nenhum microfone selecionado.",
            size=13,
            weight=ft.FontWeight.W_600,
            color=PASTEL_DARK_PURPLE,
        )
        self.test_microphone_button = build_primary_button(
            "Testar microfone",
            self.on_test_microphone,
            visible=False,
        )
        self.audio_visualizer = AudioVisualizer()
        self.status_card: ft.Container | None = None
        self.fields: dict[str, ft.Control] = {}
        self.field_wrappers: dict[str, ft.Container] = {}
        self.root: VoiceSettingsContent | None = None
        self.audio_device_service = AudioDeviceService()
        self.saved_microphone_index = self.settings.input_device_index
        self.selected_microphone_id: str | None = None
        self._microphones_by_id: dict[str, Microphone] = {}
        self._microphones_loaded = False
        self._update_selected_microphone_status()
        self.reload_microphones_button = build_primary_button(
            "Recarregar",
            self.on_reload_microphones,
            expand=True,
        )
        self.delete_microphone_button = build_primary_button(
            "Apagar Microfone",
            self.on_delete_microphone,
            expand=True,
        )
        self._level_monitor: MicrophoneLevelMonitor | None = None
        self._level_monitor_token = 0
        self._level_monitor_selection: str | None = None

    def build(self) -> ft.Column:
        self.field_wrappers = {}
        self.fields = self._build_fields()
        self.status_card = self._build_status_card()

        self.root = VoiceSettingsContent(
            on_mount=self.load_microphones,
            on_unmount=self.stop_microphone_services,
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
                        self._field_grid("enabled", "mode", "input_device_index"),
                        self._field_grid("language", "model_size", "realtime_model_size", "device", "compute_type"),
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
                        build_primary_button("Salvar", self.on_save)
                    ],
                ),
            ],
        )
        return self.root

    def _build_fields(self) -> dict[str, ft.Control]:
        settings = self.settings
        return {
            "enabled": self._switch("Ativar comandos por voz", settings.enabled),
            "mode": build_dropdown(
                "Modo de reconhecimento",
                settings.mode,
                (("basic", "Básico - Faster-Whisper"), ("realtime", "Tempo real - RealtimeSTT + Faster-Whisper")),
                on_select=self.on_mode_change,
            ),
            "language": build_dropdown(
                "Idioma",
                settings.language,
                (("pt", "Português"), ("", "Detecção automática"), ("en", "Inglês"), ("es", "Espanhol")),
            ),
            "model_size": build_dropdown("Modelo final", settings.model_size, tuple((x, x) for x in MODEL_OPTIONS)),
            "realtime_model_size": build_dropdown(
                "Modelo em tempo real", settings.realtime_model_size, tuple((x, x) for x in MODEL_OPTIONS)
            ),
            "device": build_dropdown(
                "Processamento",
                settings.device,
                (("cpu", "CPU"), ("cuda", "GPU NVIDIA (CUDA)"), ("auto", "Automático")),
            ),
            "compute_type": build_dropdown(
                "Precisão",
                settings.compute_type,
                (("int8", "int8 - leve"), ("float16", "float16"), ("float32", "float32"), ("default", "Padrão do dispositivo")),
            ),
            "input_device_index": build_dropdown(
                "Microfone",
                "",
                (),
                helper="Clique em Recarregar para consultar os microfones.",
                disabled=True,
                menu_width=MICROPHONE_DROPDOWN_MENU_WIDTH,
                menu_height=MICROPHONE_DROPDOWN_MENU_HEIGHT,
                on_select=self.on_microphone_select,
            ),
            "sample_rate": build_text_field("Taxa de amostragem (Hz)", str(settings.sample_rate)),
            "audio_threshold": build_text_field("Limiar de áudio", str(settings.audio_threshold)),
            "silence_duration": build_text_field("Silêncio para encerrar a frase (s)", str(settings.silence_duration)),
            "min_recording_duration": build_text_field("Duração mínima da fala (s)", str(settings.min_recording_duration)),
            "realtime_processing_pause": build_text_field(
                "Intervalo das atualizações parciais (s)", str(settings.realtime_processing_pause)
            ),
            "beam_size": build_text_field("Beam size final", str(settings.beam_size)),
            "realtime_beam_size": build_text_field("Beam size em tempo real", str(settings.realtime_beam_size)),
            "batch_size": build_text_field("Batch size final", str(settings.batch_size)),
            "realtime_batch_size": build_text_field("Batch size em tempo real", str(settings.realtime_batch_size)),
            "vad_filter": self._switch("Ativar filtro de atividade de voz (VAD)", settings.vad_filter),
            "silero_sensitivity": build_text_field("Sensibilidade Silero (0 a 1)", str(settings.silero_sensitivity)),
            "webrtc_sensitivity": build_text_field("Agressividade WebRTC (0 a 3)", str(settings.webrtc_sensitivity)),
            "proper_names": build_text_field("Nomes próprios", settings.proper_names, multiline=True),
            "context": build_text_field("Contexto adicional", settings.context, multiline=True),
            "hotwords": build_text_field("Palavras importantes", settings.hotwords, multiline=True),
            "condition_on_previous_text": self._switch(
                "Usar o texto anterior como contexto no modo básico", settings.condition_on_previous_text
            ),
            "temperature": build_text_field("Temperatura (0 a 1)", str(settings.temperature)),
        }

    def load_microphones(self) -> None:
        root = self.root
        if root is None or not self._is_mounted(root):
            return
        try:
            root.page.run_task(self._reload_microphones)
        except Exception:
            logging.exception("Não foi possível carregar os microfones.")

    def stop_microphone_services(self) -> None:
        self._stop_level_monitor()

    def on_reload_microphones(self, event: ft.ControlEvent | None = None) -> None:
        root = self.root
        if root is None or not self._is_mounted(root):
            return
        try:
            root.page.run_task(self._reload_microphones)
        except Exception:
            logging.exception("Não foi possível recarregar os microfones.")

    async def _reload_microphones(self) -> None:
        microphone_field = self.fields.get("input_device_index")
        if not isinstance(microphone_field, ft.Dropdown):
            return

        self.reload_microphones_button.disabled = True
        self._update_microphone_controls()
        try:
            microphones = await asyncio.to_thread(self.audio_device_service.get_microphones)
        except Exception as error:
            logging.warning("Falha ao listar microfones: %s", error)
            microphones = []
            self.toaster_handler.show_error(str(error), title="Microfones indisponíveis")
        finally:
            self.reload_microphones_button.disabled = False

        self._apply_microphones(microphones)

    def _apply_microphones(self, microphones: list[Microphone]) -> None:
        microphone_field = self.fields.get("input_device_index")
        if not isinstance(microphone_field, ft.Dropdown):
            return

        self._microphones_by_id = {microphone["id"]: microphone for microphone in microphones}
        available_ids = set(self._microphones_by_id)
        selected_id = self.selected_microphone_id
        saved_microphone_id = self._saved_microphone_id()
        must_clear_saved_microphone = False

        if not self._microphones_loaded:
            selected_id = selected_id if selected_id is not None else saved_microphone_id
            must_clear_saved_microphone = (
                self.saved_microphone_index is not None and saved_microphone_id is None
            )
            self._microphones_loaded = True
        elif selected_id is None:
            selected_id = saved_microphone_id
        elif selected_id not in available_ids and selected_id != DEFAULT_MICROPHONE_ID:
            selected_id = saved_microphone_id
            must_clear_saved_microphone = (
                self.saved_microphone_index is not None and saved_microphone_id is None
            )

        if not microphones:
            selected_id = None
            must_clear_saved_microphone = self.saved_microphone_index is not None

        self.selected_microphone_id = selected_id
        microphone_field.options = (
            [
                ft.DropdownOption(key=DEFAULT_MICROPHONE_ID, text="Microfone padrão do sistema"),
                *[
                    ft.DropdownOption(key=microphone["id"], text=microphone["name"])
                    for microphone in microphones
                ],
            ]
            if microphones
            else []
        )
        microphone_field.value = selected_id
        microphone_field.disabled = not microphones
        microphone_helper = (
            f"{len(microphones)} microfone(s) disponível(is)."
            if microphones
            else "Nenhum microfone conectado."
        )
        microphone_field.helper_text = microphone_helper
        microphone_field.tooltip = build_tooltip_message(microphone_helper, width=TOOLTIP_LINE_WIDTH)

        if must_clear_saved_microphone:
            self._clear_saved_microphone(show_toast=False)

        self._update_microphone_controls()
        self._update_selected_microphone_status()
        self._start_level_monitor_for_selection()

    def on_microphone_select(self, event: ft.ControlEvent | None = None) -> None:
        microphone_field = self.fields.get("input_device_index")
        if isinstance(microphone_field, ft.Dropdown):
            self.selected_microphone_id = microphone_field.value
            if self.selected_microphone_id is None:
                self._clear_saved_microphone(show_toast=False)
        self._update_selected_microphone_status()
        self._start_level_monitor_for_selection()

    def on_delete_microphone(self, event: ft.ControlEvent | None = None) -> None:
        self.selected_microphone_id = None
        microphone_field = self.fields.get("input_device_index")
        if isinstance(microphone_field, ft.Dropdown):
            microphone_field.value = self.selected_microphone_id
        self._clear_saved_microphone(show_toast=True)
        self._update_selected_microphone_status()
        self._update_microphone_controls()
        self._start_level_monitor_for_selection()

    def _clear_saved_microphone(self, *, show_toast: bool) -> None:
        if self.saved_microphone_index is None:
            if show_toast:
                self.toaster_handler.show_success(
                    "O microfone salvo já está definido como padrão do sistema.",
                    title="Configuração de voz",
                )
            return
        try:
            self.settings = self.settings_service.save(
                replace(self.settings, input_device_index=None)
            )
            self.saved_microphone_index = None
        except Exception as error:
            logging.exception("Não foi possível remover o microfone salvo.")
            self.toaster_handler.show_error(str(error), title="Erro ao remover microfone")
            return
        if show_toast:
            self.toaster_handler.show_success(
                "Microfone removido. A IRIS usará o padrão do sistema.",
                title="Configuração de voz",
            )

    def _update_microphone_controls(self) -> None:
        microphone_field = self.fields.get("input_device_index")
        controls = (microphone_field, self.reload_microphones_button, self.delete_microphone_button)
        for control in controls:
            if control is not None and self._is_mounted(control):
                control.update()

    def _update_selected_microphone_status(self) -> None:
        effective_microphone_id = self._effective_microphone_id()
        if effective_microphone_id is None:
            if self.selected_microphone_id is None and self.saved_microphone_index is not None:
                self.selected_microphone_text.value = f"Microfone salvo: entrada {self.saved_microphone_index}."
                self.selected_microphone_text.color = PASTEL_DARK_PURPLE
            else:
                self.selected_microphone_text.value = "Nenhum microfone conectado."
                self.selected_microphone_text.color = TEXT_SECONDARY
        elif effective_microphone_id == DEFAULT_MICROPHONE_ID:
            self.selected_microphone_text.value = (
                "Microfone selecionado: padrão do sistema."
            )
            self.selected_microphone_text.color = PASTEL_DARK_PURPLE
        else:
            microphone = self._microphones_by_id.get(effective_microphone_id)
            name = microphone["name"] if microphone else "indisponível"
            self.selected_microphone_text.value = f"Microfone selecionado: {name}."
            self.selected_microphone_text.color = PASTEL_DARK_PURPLE

        if self._is_mounted(self.selected_microphone_text):
            self.selected_microphone_text.update()

    def _effective_microphone_id(self) -> str | None:
        if self.selected_microphone_id is not None:
            return self.selected_microphone_id
        return self._saved_microphone_id()

    def _saved_microphone_id(self) -> str | None:
        if self.saved_microphone_index is None:
            return None
        return next(
            (
                microphone["id"]
                for microphone in self._microphones_by_id.values()
                if microphone["index"] == self.saved_microphone_index
            ),
            None,
        )

    def _start_level_monitor_for_selection(self) -> None:
        root = self.root
        microphone_field = self.fields.get("input_device_index")
        if root is None or not self._is_mounted(root) or not isinstance(microphone_field, ft.Dropdown):
            return

        selection = self._effective_microphone_id()
        saved_selection_key = (
            f"saved:{self.saved_microphone_index}"
            if selection is None and self.selected_microphone_id is None and self.saved_microphone_index is not None
            else None
        )
        monitor_selection = selection if selection is not None else saved_selection_key
        if monitor_selection is None or (microphone_field.disabled and saved_selection_key is None):
            self._stop_level_monitor()
            self.audio_visualizer.set_level(0.0)
            return
        if monitor_selection == self._level_monitor_selection and self._level_monitor is not None:
            return

        self._stop_level_monitor()
        selected_microphone = self._microphones_by_id.get(selection or "")
        self._level_monitor_selection = monitor_selection
        monitor = MicrophoneLevelMonitor(
            self._on_microphone_level,
            input_device_index=(
                self.saved_microphone_index
                if saved_selection_key is not None
                else selected_microphone["index"] if selected_microphone else None
            ),
            sample_rate=self._current_sample_rate(),
            on_error=self._on_microphone_level_error,
        )
        self._level_monitor = monitor
        self._level_monitor_token += 1
        try:
            root.page.run_task(self._run_level_monitor, monitor, self._level_monitor_token)
        except Exception:
            logging.exception("Não foi possível iniciar o visualizador do microfone.")

    def _stop_level_monitor(self) -> None:
        self._level_monitor_token += 1
        if self._level_monitor is not None:
            self._level_monitor.stop()
        self._level_monitor = None
        self._level_monitor_selection = None

    async def _run_level_monitor(self, monitor: MicrophoneLevelMonitor, token: int) -> None:
        try:
            await monitor.start()
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Falha no monitor de nível do microfone.")
        finally:
            if token == self._level_monitor_token:
                self._level_monitor = None

    def _on_microphone_level(self, level: float) -> None:
        try:
            page = self.audio_visualizer.root.page
        except RuntimeError:
            return
        if page is not None:
            try:
                page.run_task(self._apply_microphone_level, level)
            except Exception:
                logging.exception("Não foi possível atualizar o visualizador do microfone.")

    def _on_microphone_level_error(self) -> None:
        try:
            page = self.audio_visualizer.root.page
        except RuntimeError:
            return
        if page is not None:
            try:
                page.run_task(self._apply_microphone_level_error)
            except Exception:
                logging.exception("Não foi possível aplicar o fallback do microfone.")

    async def _apply_microphone_level(self, level: float) -> None:
        try:
            self.audio_visualizer.set_level(level)
            if self._is_mounted(self.audio_visualizer.root):
                self.audio_visualizer.root.update()
        except Exception:
            logging.exception("Falha ao atualizar o visualizador do microfone.")

    async def _apply_microphone_level_error(self) -> None:
        try:
            microphone_field = self.fields.get("input_device_index")
            if not isinstance(microphone_field, ft.Dropdown) or microphone_field.disabled:
                return

            self._stop_level_monitor()
            self.audio_visualizer.set_level(0.0)
            microphone_helper = (
                "O microfone continua selecionado, mas não foi possível ler o áudio. "
                "Clique em Recarregar para consultar os dispositivos novamente."
            )
            microphone_field.helper_text = microphone_helper
            microphone_field.tooltip = build_tooltip_message(microphone_helper, width=TOOLTIP_LINE_WIDTH)
            self._update_microphone_controls()
            if self._is_mounted(self.audio_visualizer.root):
                self.audio_visualizer.root.update()
        except Exception:
            logging.exception("Falha ao informar o erro do microfone selecionado.")

    def _current_sample_rate(self) -> int:
        raw_value = str(self._field_value("sample_rate") or self.settings.sample_rate).strip()
        try:
            return int(raw_value)
        except ValueError:
            return self.settings.sample_rate

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
                    ft.Column(
                        expand=True,
                        tight=True,
                        spacing=2,
                        controls=[self.selected_microphone_text, self.status_text],
                    ),
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
        controls: list[ft.Control] = []
        for field_name in field_names:
            if field_name == "input_device_index":
                controls.extend(self._build_microphone_grid_controls())
                continue
            controls.append(self._build_field_wrapper(field_name))

        return ft.ResponsiveRow(
            spacing=18,
            run_spacing=24,
            controls=controls,
        )

    def _build_microphone_grid_controls(self) -> list[ft.Control]:
        return [
            self._build_field_wrapper("input_device_index", md_columns=6),
            ft.Container(
                expand=True,
                col={"md": 6},
                visible=self._is_field_visible("input_device_index"),
                content=ft.Row(
                    expand=True,
                    spacing=13,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        self.reload_microphones_button,
                        self.delete_microphone_button,
                    ],
                ),
            ),
        ]

    def _build_field_wrapper(self, field_name: str, *, md_columns: int = 6) -> ft.Container:
        field_controls: list[ft.Control] = [
            ft.Container(expand=True, content=self.fields[field_name]),
        ]
        field_controls.append(
            ft.Container(
                width=25,
                height=25,
                border_radius=20,
                alignment=ft.Alignment.CENTER,
                bgcolor=BLUE_GREY,

                tooltip=ft.Tooltip(
                    message=build_tooltip_message(FIELD_HELP[field_name], width=TOOLTIP_LINE_WIDTH),
                    bgcolor=BLUE_GREY,
                    text_style=ft.TextStyle(size=12, color=TEXT_PRIMARY),
                    padding=12,
                ),
                content=ft.Icon(
                    ft.Icons.INFO_OUTLINE_ROUNDED,
                    color=PASTEL_PURPLE,
                    size=15,
                ),
            )
        )
        wrapper = ft.Container(
            expand=True,
            col={"sm": 12, "md": md_columns},
            visible=self._is_field_visible(field_name),
            content=ft.Row(
                expand=True,
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=field_controls,
            ),
        )
        self.field_wrappers[field_name] = wrapper
        return wrapper

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
            expand=True,
            height=58,
            padding=ft.Padding(left=12, top=0, right=12, bottom=0),
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            alignment=ft.Alignment.CENTER_LEFT,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[ft.Text(label, size=13, color=TEXT_PRIMARY, expand=True), switch],
            ),
            data=switch,
        )

    def on_save(self, event=None) -> None:
        try:
            values = self._read_form()
            self.settings = self.settings_service.save(values)
            self.saved_microphone_index = self.settings.input_device_index
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
        microphone_id = str(value("input_device_index") or "").strip()
        microphone = self._microphones_by_id.get(microphone_id)
        return replace(
            self.settings,
            enabled=bool(value("enabled")),
            mode=str(value("mode")),
            language=str(value("language") or ""),
            model_size=str(value("model_size")),
            realtime_model_size=str(value("realtime_model_size")),
            device=str(value("device")),
            compute_type=str(value("compute_type")),
            input_device_index=microphone["index"] if microphone else None,
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
            try:
                page.run_task(self._apply_speech_event, event)
            except Exception:
                logging.exception("Não foi possível encaminhar o evento de voz para a configuração.")

    async def _apply_speech_event(self, event: SpeechEvent) -> None:
        try:
            if event.kind == SpeechEventKind.AUDIO_LEVEL:
                return
            if event.kind == SpeechEventKind.TRANSCRIPTION:
                return

            if event.kind == SpeechEventKind.ERROR:
                self.status_text.value = event.message
                self.status_text.color = ft.Colors.RED_700
                self.test_microphone_button.visible = False
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
                if not self.settings.enabled:
                    self.status_text.value = "Voz desativada"
                    self.status_text.color = TEXT_SECONDARY

            if self._is_mounted(self.status_text):
                self.status_card.update()
                if event.kind in {SpeechEventKind.ERROR, SpeechEventKind.STOPPED}:
                    self.audio_visualizer.root.update()
        except Exception:
            logging.exception("Falha ao atualizar o estado do serviço de voz.")

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
