from __future__ import annotations

import logging
import queue
import re
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from services.voice_settings import VoiceSettings


WAKE_WORD_PATTERN = re.compile(r"\b[ií]ris\b", re.IGNORECASE)
LEADING_WAKE_WORD_PATTERN = re.compile(r"^\s*[ií]ris\b[\s,.!?;:-]*", re.IGNORECASE)
SEND_WORD_PATTERN = re.compile(r"(?:^|\s)enviar[.!?,;:]*\s*$", re.IGNORECASE)
MAX_BASIC_UTTERANCE_SECONDS = 30.0


class SpeechEventKind(StrEnum):
    STARTING = "starting"
    READY = "ready"
    CAPTURE_STARTED = "capture_started"
    CAPTURE_FINISHED = "capture_finished"
    ACTIVATED = "activated"
    PARTIAL = "partial"
    FINAL = "final"
    DEACTIVATED = "deactivated"
    STOPPED = "stopped"
    ERROR = "error"
    AUDIO_LEVEL = "audio_level"
    TRANSCRIPTION = "transcription"


@dataclass(frozen=True, slots=True)
class SpeechEvent:
    kind: SpeechEventKind
    text: str = ""
    message: str = ""
    should_submit: bool = False
    source: str = ""
    is_partial: bool = False
    audio_level: float = 0.0


SpeechEventCallback = Callable[[SpeechEvent], None]


class NoInputDeviceError(RuntimeError):
    """Indica que não existe uma entrada de áudio utilizável."""


class SpeechService(ABC):
    """Contrato comum para captura e transcrição local de voz."""

    def __init__(self, settings: VoiceSettings, on_event: SpeechEventCallback | None = None):
        self.settings = settings
        self._on_event = on_event
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._command_enabled = True
        self._last_audio_event_at = 0.0
        self._voice_active = False
        self._last_command = ""
        self._committed_command = ""

    @property
    def is_running(self) -> bool:
        return bool(self._worker and self._worker.is_alive())

    def start(self) -> None:
        if self.is_running:
            return

        self._stop_event.clear()
        self._worker = threading.Thread(
            target=self._run_safely,
            name=self.__class__.__name__,
            daemon=True,
        )
        self._worker.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._request_backend_stop()
        worker = self._worker
        if worker and worker is not threading.current_thread():
            worker.join(timeout=3)
        self._worker = None
        self._voice_active = False
        self._last_command = ""
        self._committed_command = ""

    def deactivate_command(self) -> None:
        if not self._voice_active:
            return
        self._voice_active = False
        self._last_command = ""
        self._committed_command = ""
        self._emit(SpeechEventKind.DEACTIVATED)

    def set_command_enabled(self, enabled: bool) -> None:
        """Permite a palavra de ativação somente no contexto visual autorizado."""
        self._command_enabled = enabled
        if not enabled:
            self.deactivate_command()

    def process_transcription(self, text: str, *, is_partial: bool) -> None:
        """Converte transcrições do backend em eventos de comando da IRIS."""
        if not self._command_enabled:
            return

        cleaned_text = " ".join((text or "").strip().split())
        if not cleaned_text:
            return

        command_text = cleaned_text
        repeated_wake_word = False
        if not self._voice_active:
            wake_word = WAKE_WORD_PATTERN.search(cleaned_text)
            if wake_word is None:
                return

            self._voice_active = True
            self._emit(SpeechEventKind.ACTIVATED)
            command_text = cleaned_text[wake_word.end():].lstrip(" ,.!?;:-")
        else:
            repeated_wake_word = bool(LEADING_WAKE_WORD_PATTERN.search(cleaned_text))
            command_text = LEADING_WAKE_WORD_PATTERN.sub("", cleaned_text, count=1).lstrip(" ,.!?;:-")
            if repeated_wake_word:
                self._committed_command = ""

        has_send_word = bool(SEND_WORD_PATTERN.search(command_text))
        should_submit = has_send_word and not is_partial
        if has_send_word:
            command_text = SEND_WORD_PATTERN.sub("", command_text)
        command_text = command_text.strip(" ,.!?;:-")
        if command_text and self._committed_command and not repeated_wake_word:
            current_command = f"{self._committed_command} {command_text}".strip()
        else:
            current_command = command_text or self._committed_command or self._last_command

        if current_command:
            self._last_command = current_command
            self._emit(
                SpeechEventKind.PARTIAL if is_partial and not should_submit else SpeechEventKind.FINAL,
                text=current_command,
                should_submit=should_submit,
            )
            if not is_partial and not should_submit:
                self._committed_command = current_command

        if should_submit:
            self.deactivate_command()

    def _run_safely(self) -> None:
        self._emit(SpeechEventKind.STARTING, message="Preparando reconhecimento de voz...")
        try:
            self._run()
        except Exception as error:
            if isinstance(error, NoInputDeviceError):
                logging.warning("Serviço de voz interrompido: %s", error)
            else:
                logging.exception("Falha no serviço de voz")
            if not self._stop_event.is_set():
                self._emit(SpeechEventKind.ERROR, message=self._friendly_error(error))
        finally:
            self._emit(SpeechEventKind.STOPPED)

    def _emit(
        self,
        kind: SpeechEventKind,
        *,
        text: str = "",
        message: str = "",
        should_submit: bool = False,
        source: str = "",
        is_partial: bool = False,
        audio_level: float = 0.0,
    ) -> None:
        if self._on_event is not None:
            self._on_event(
                SpeechEvent(
                    kind=kind,
                    text=text,
                    message=message,
                    should_submit=should_submit,
                    source=source,
                    is_partial=is_partial,
                    audio_level=audio_level,
                )
            )

    def _emit_transcription(self, text: str, *, source: str, is_partial: bool) -> None:
        cleaned_text = " ".join((text or "").strip().split())
        if cleaned_text:
            self._emit(
                SpeechEventKind.TRANSCRIPTION,
                text=cleaned_text,
                source=source,
                is_partial=is_partial,
            )

    def _emit_audio_level(self, volume: float, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_audio_event_at < 0.08:
            return
        self._last_audio_event_at = now
        reference = max(self.settings.audio_threshold * 2, 0.02)
        normalized_level = max(0.0, min(1.0, float(volume) / reference))
        self._emit(SpeechEventKind.AUDIO_LEVEL, audio_level=normalized_level)

    def _friendly_error(self, error: Exception) -> str:
        message = str(error).strip()
        lowered = message.lower()
        if "no module named" in lowered:
            return "Dependências de voz não instaladas. Execute a instalação do requirements.txt."
        if "device" in lowered or "microphone" in lowered or "portaudio" in lowered:
            return "Não foi possível acessar o microfone. Verifique o dispositivo e as permissões do Windows."
        return message or "Não foi possível iniciar o reconhecimento de voz."

    def _resolve_input_device_index(self) -> int:
        """Retorna o dispositivo salvo ou o padrão, se houver uma entrada válida."""
        import sounddevice as sd

        input_device_index = self.settings.input_device_index
        if input_device_index is not None:
            try:
                device_info = sd.query_devices(input_device_index)
                if int(device_info.get("max_input_channels", 0)) > 0:
                    return input_device_index
                raise ValueError("O dispositivo salvo não possui entrada de áudio.")
            except Exception as error:
                logging.warning(
                    "Microfone salvo indisponível (%s). Usando o microfone padrão do sistema.",
                    error,
                )

        default_device = sd.default.device
        if isinstance(default_device, (list, tuple)):
            default_device = default_device[0] if default_device else None
        try:
            default_index = int(default_device)
        except (TypeError, ValueError):
            default_index = -1

        if default_index < 0:
            raise NoInputDeviceError(
                "Nenhum microfone disponível. Conecte um microfone ou selecione um dispositivo válido."
            )

        try:
            device_info = sd.query_devices(default_index)
            if int(device_info.get("max_input_channels", 0)) <= 0:
                raise ValueError("O dispositivo padrão não possui entrada de áudio.")
            return default_index
        except Exception as error:
            raise NoInputDeviceError(
                "Nenhum microfone disponível. Conecte um microfone ou selecione um dispositivo válido."
            ) from error

    def _request_backend_stop(self) -> None:
        return

    @abstractmethod
    def _run(self) -> None:
        raise NotImplementedError


class FasterWhisperSpeechService(SpeechService):
    """Modo básico: captura uma frase e transcreve somente após o silêncio."""

    def __init__(self, settings: VoiceSettings, on_event: SpeechEventCallback | None = None):
        super().__init__(settings, on_event)
        self._model: Any = None
        self._audio_queue: queue.Queue[Any] = queue.Queue(maxsize=100)

    def _run(self) -> None:
        import numpy as np
        import sounddevice as sd
        from faster_whisper import WhisperModel

        input_device_index = self._resolve_input_device_index()
        if self._model is None:
            self._model = WhisperModel(
                self.settings.model_size,
                device=self.settings.device,
                compute_type=self.settings.compute_type,
            )

        block_size = max(512, int(self.settings.sample_rate * 0.1))
        pre_roll_blocks = max(1, int(0.5 * self.settings.sample_rate / block_size))
        pre_roll: deque[Any] = deque(maxlen=pre_roll_blocks)
        audio_buffer: list[Any] = []
        silence_duration = 0.0
        recording_duration = 0.0
        is_speaking = False
        is_transcribing = False

        def finish_utterance() -> None:
            nonlocal audio_buffer, silence_duration, recording_duration, is_speaking, is_transcribing
            if not audio_buffer:
                return
            audio = np.concatenate(audio_buffer, axis=0).flatten()
            audio_buffer = []
            silence_duration = 0.0
            recording_duration = 0.0
            is_speaking = False
            is_transcribing = True
            self._emit_audio_level(0.0, force=True)
            try:
                self._transcribe_audio(audio)
            finally:
                is_transcribing = False
                self._emit(SpeechEventKind.CAPTURE_FINISHED)
                while not self._audio_queue.empty():
                    try:
                        self._audio_queue.get_nowait()
                    except queue.Empty:
                        break

        def on_audio(indata, frames, time_info, status) -> None:
            if status:
                logging.warning("Captura de voz: %s", status)
            if is_transcribing:
                return
            try:
                self._audio_queue.put_nowait(indata.copy())
            except queue.Full:
                logging.warning("Buffer do microfone cheio; bloco de áudio descartado.")

        stream_options: dict[str, Any] = {
            "samplerate": self.settings.sample_rate,
            "channels": 1,
            "callback": on_audio,
            "dtype": "float32",
            "blocksize": block_size,
        }
        stream_options["device"] = input_device_index

        with sd.InputStream(**stream_options):
            self._emit(SpeechEventKind.READY, message="Voz pronta. Diga “IRIS” para começar.")
            while not self._stop_event.is_set():
                try:
                    data = self._audio_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                volume = float(np.sqrt(np.mean(data**2)))
                self._emit_audio_level(volume)
                if volume > self.settings.audio_threshold:
                    if not is_speaking:
                        audio_buffer = list(pre_roll)
                        pre_roll.clear()
                        self._emit(SpeechEventKind.CAPTURE_STARTED)
                    is_speaking = True
                    silence_duration = 0.0
                    audio_buffer.append(data)
                    recording_duration += len(data) / self.settings.sample_rate
                    if recording_duration >= MAX_BASIC_UTTERANCE_SECONDS:
                        finish_utterance()
                    continue

                if not is_speaking:
                    pre_roll.append(data)
                    continue

                audio_buffer.append(data)
                block_duration = len(data) / self.settings.sample_rate
                silence_duration += block_duration
                recording_duration += block_duration
                if silence_duration < self.settings.silence_duration:
                    continue
                finish_utterance()

    def _transcribe_audio(self, audio: Any) -> None:
        segments, _ = self._model.transcribe(
            audio,
            language=self.settings.language or None,
            initial_prompt=self.settings.build_initial_prompt(),
            hotwords=self.settings.hotwords or None,
            beam_size=self.settings.beam_size,
            temperature=self.settings.temperature,
            condition_on_previous_text=self.settings.condition_on_previous_text,
            vad_filter=self.settings.vad_filter,
        )
        text = "".join(segment.text for segment in segments).strip()
        self._emit_transcription(text, source="faster_whisper", is_partial=False)
        self.process_transcription(text, is_partial=False)


class RealtimeSpeechService(SpeechService):
    """Modo avançado: RealtimeSTT com Faster-Whisper parcial e final."""

    def __init__(self, settings: VoiceSettings, on_event: SpeechEventCallback | None = None):
        super().__init__(settings, on_event)
        self._recorder: Any = None

    def _run(self) -> None:
        from RealtimeSTT import AudioToTextRecorder

        prompt = self.settings.build_initial_prompt()
        self._recorder = AudioToTextRecorder(
            transcription_engine="faster_whisper",
            model=self.settings.model_size,
            realtime_model_type=self.settings.realtime_model_size,
            device=self.settings.device,
            compute_type=self.settings.compute_type,
            language=self.settings.language,
            input_device_index=self._resolve_input_device_index(),
            sample_rate=self.settings.sample_rate,
            beam_size=self.settings.beam_size,
            beam_size_realtime=self.settings.realtime_beam_size,
            batch_size=self.settings.batch_size,
            realtime_batch_size=self.settings.realtime_batch_size,
            initial_prompt=prompt,
            initial_prompt_realtime=prompt,
            enable_realtime_transcription=True,
            realtime_processing_pause=self.settings.realtime_processing_pause,
            post_speech_silence_duration=self.settings.silence_duration,
            min_length_of_recording=self.settings.min_recording_duration,
            silero_sensitivity=self.settings.silero_sensitivity,
            webrtc_sensitivity=self.settings.webrtc_sensitivity,
            faster_whisper_vad_filter=self.settings.vad_filter,
            on_realtime_transcription_update=self._on_partial,
            on_recorded_chunk=self._on_audio_chunk,
            ensure_sentence_ends_with_period=False,
            spinner=False,
            no_log_file=True,
        )
        self._emit(SpeechEventKind.READY, message="Voz em tempo real pronta. Diga “IRIS” para começar.")

        while not self._stop_event.is_set():
            self._recorder.text(self._on_final)

    def _on_partial(self, text: str) -> None:
        if not self._stop_event.is_set():
            self._emit_transcription(text, source="realtime_stt", is_partial=True)
            self.process_transcription(text, is_partial=True)

    def _on_final(self, text: str) -> None:
        if not self._stop_event.is_set():
            self._emit_transcription(text, source="faster_whisper", is_partial=False)
            self.process_transcription(text, is_partial=False)

    def _on_audio_chunk(self, data: Any) -> None:
        if self._stop_event.is_set():
            return
        try:
            import numpy as np

            if isinstance(data, (bytes, bytearray, memoryview)):
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                samples = np.asarray(data)
                if np.issubdtype(samples.dtype, np.integer):
                    samples = samples.astype(np.float32) / max(float(np.iinfo(samples.dtype).max), 1.0)
            if samples.size:
                self._emit_audio_level(float(np.sqrt(np.mean(samples.astype(np.float32) ** 2))))
        except Exception:
            logging.debug("Não foi possível calcular o nível do áudio do RealtimeSTT.", exc_info=True)

    def _request_backend_stop(self) -> None:
        recorder = self._recorder
        if recorder is not None:
            try:
                recorder.shutdown()
            except Exception:
                logging.exception("Falha ao encerrar o RealtimeSTT")
            finally:
                self._recorder = None
