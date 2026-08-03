from __future__ import annotations

from dataclasses import dataclass


FIXED_IRIS_PROMPT = "Nome de pessoa: Íris, Iris. A Íris falou que vai participar."


@dataclass(frozen=True, slots=True)
class VoiceSettings:
    enabled: bool = False
    mode: str = "basic"
    language: str = "pt"
    model_size: str = "small"
    realtime_model_size: str = "tiny"
    device: str = "cpu"
    compute_type: str = "int8"
    input_device_index: int | None = None
    sample_rate: int = 16000
    audio_threshold: float = 0.025
    silence_duration: float = 1.2
    min_recording_duration: float = 0.5
    realtime_processing_pause: float = 0.3
    beam_size: int = 5
    realtime_beam_size: int = 3
    batch_size: int = 0
    realtime_batch_size: int = 0
    vad_filter: bool = True
    silero_sensitivity: float = 0.4
    webrtc_sensitivity: int = 3
    proper_names: str = ""
    context: str = ""
    hotwords: str = ""
    condition_on_previous_text: bool = True
    temperature: float = 0.0

    def validate(self) -> "VoiceSettings":
        if self.mode not in {"basic", "realtime"}:
            raise ValueError("Selecione um modo de voz válido.")
        if self.device not in {"cpu", "cuda", "auto"}:
            raise ValueError("Selecione um dispositivo de processamento válido.")
        if not 8000 <= self.sample_rate <= 48000:
            raise ValueError("A taxa de amostragem deve ficar entre 8.000 e 48.000 Hz.")
        if not 0 < self.audio_threshold <= 1:
            raise ValueError("O limiar de áudio deve ficar entre 0 e 1.")
        if not 0.2 <= self.silence_duration <= 10:
            raise ValueError("O tempo de silêncio deve ficar entre 0,2 e 10 segundos.")
        if not 0.1 <= self.realtime_processing_pause <= 5:
            raise ValueError("O intervalo em tempo real deve ficar entre 0,1 e 5 segundos.")
        if not 1 <= self.beam_size <= 20 or not 1 <= self.realtime_beam_size <= 20:
            raise ValueError("Beam size deve ficar entre 1 e 20.")
        if not 0 <= self.batch_size <= 64 or not 0 <= self.realtime_batch_size <= 64:
            raise ValueError("Batch size deve ficar entre 0 e 64.")
        if not 0 <= self.silero_sensitivity <= 1:
            raise ValueError("A sensibilidade Silero deve ficar entre 0 e 1.")
        if not 0 <= self.webrtc_sensitivity <= 3:
            raise ValueError("A sensibilidade WebRTC deve ficar entre 0 e 3.")
        if not 0 <= self.temperature <= 1:
            raise ValueError("A temperatura deve ficar entre 0 e 1.")
        return self

    def build_initial_prompt(self) -> str:
        parts = [FIXED_IRIS_PROMPT]
        if self.proper_names.strip():
            parts.append(f"Nomes próprios: {self.proper_names.strip()}.")
        if self.context.strip():
            parts.append(self.context.strip())
        if self.hotwords.strip():
            parts.append(f"Palavras importantes: {self.hotwords.strip()}.")
        return " ".join(parts)
