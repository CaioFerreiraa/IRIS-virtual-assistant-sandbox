from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from typing import TypedDict

import numpy as np


VIRTUAL_MICROPHONE_NAMES = (
    "microsoft sound mapper",
    "primary sound capture driver",
    "driver de captura de som",
    "mapeador de som microsoft",
    "stereo mix",
    "mixagem estéreo",
    "mixagem",
    "stereo",
    "line input",
    "entrada",
)


class Microphone(TypedDict):
    id: str
    index: int
    name: str
    host_api: int
    host_api_name: str
    channels: int
    sample_rate: int


class AudioDeviceService:
    """Lista microfones disponíveis sem manter um monitor em segundo plano."""

    @staticmethod
    def get_microphones() -> list[Microphone]:
        try:
            import sounddevice as sd
        except ImportError as error:
            raise RuntimeError(
                "O sounddevice não está instalado. Instale as dependências da aplicação para listar microfones."
            ) from error

        try:
            devices = sd.query_devices()
            host_apis = sd.query_hostapis()
        except Exception as error:
            raise RuntimeError(
                "Não foi possível acessar os dispositivos de áudio do sistema."
            ) from error

        try:
            microphones: list[Microphone] = []
            for index, device in enumerate(devices):
                if int(device["max_input_channels"]) <= 0:
                    continue

                name = str(device["name"])
                host_api = int(device["hostapi"])
                host_api_name = (
                    str(host_apis[host_api]["name"])
                    if 0 <= host_api < len(host_apis)
                    else ""
                )
                if AudioDeviceService._is_virtual_microphone(name):
                    continue
                microphones.append(
                    {
                        "id": f"{host_api}:{index}:{name}",
                        "index": index,
                        "name": name,
                        "host_api": host_api,
                        "host_api_name": host_api_name,
                        "channels": int(device["max_input_channels"]),
                        "sample_rate": int(device["default_samplerate"]),
                    }
                )
            active_microphones = AudioDeviceService._select_active_microphones(
                microphones,
                host_apis,
            )
            connected_names = AudioDeviceService._probe_connected_microphone_names()
            if connected_names is not None:
                connected_keys = {
                    AudioDeviceService._microphone_key(name)
                    for name in connected_names
                }
                active_microphones = [
                    microphone
                    for microphone in active_microphones
                    if AudioDeviceService._microphone_key(microphone["name"])
                    in connected_keys
                ]
            return AudioDeviceService._group_microphones(active_microphones)
        except Exception as error:
            raise RuntimeError(
                "Não foi possível listar os microfones conectados."
            ) from error

    @staticmethod
    def _is_virtual_microphone(name: str) -> bool:
        normalized_name = " ".join(name.casefold().split())
        return any(alias in normalized_name for alias in VIRTUAL_MICROPHONE_NAMES)

    @staticmethod
    def _select_active_microphones(
        microphones: list[Microphone],
        host_apis,
    ) -> list[Microphone]:
        """No Windows, usa somente endpoints WASAPI ativos.

        As APIs MME, DirectSound e WDM-KS podem continuar expondo conectores
        físicos vazios e aliases de dispositivos já desconectados. O WASAPI é
        a mesma fonte moderna utilizada por aplicações como navegadores.
        """
        has_wasapi = any(
            "wasapi" in str(host_api.get("name", "")).casefold()
            for host_api in host_apis
        )
        if not has_wasapi:
            return microphones
        return [
            microphone
            for microphone in microphones
            if "wasapi" in microphone["host_api_name"].casefold()
        ]

    @staticmethod
    def _probe_connected_microphone_names() -> list[str] | None:
        """Consulta o PyAudio fora do processo que mantém streams sounddevice."""
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            result = subprocess.run(
                [sys.executable, "-m", "services.pyaudio_device_probe"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
                creationflags=creation_flags,
            )
            if result.returncode != 0:
                return None
            names = json.loads(result.stdout)
            if not isinstance(names, list):
                return None
            return [str(name) for name in names if str(name).strip()]
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return None

    @staticmethod
    def _group_microphones(microphones: list[Microphone]) -> list[Microphone]:
        grouped: dict[str, Microphone] = {}
        for microphone in microphones:
            key = AudioDeviceService._microphone_key(microphone["name"])
            current = grouped.get(key)
            if current is None or AudioDeviceService._priority(microphone) < AudioDeviceService._priority(current):
                grouped[key] = microphone
        return list(grouped.values())

    @staticmethod
    def _microphone_key(name: str) -> str:
        import re
        import unicodedata

        normalized = unicodedata.normalize("NFKD", name)
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = " ".join(normalized.casefold().split())
        normalized = re.sub(r"\s*\(\s*\d+\s*-\s*", " (", normalized)
        match = re.match(r"^(.*?)\s*\((.*)\)$", normalized)
        if match and match.group(1).strip().casefold() in {"microfone", "microphone", "headset"}:
            return f"{match.group(1).strip()} ({match.group(2).strip()})"
        return re.sub(r"\s*\(.*$", "", normalized).strip() or normalized

    @staticmethod
    def _priority(microphone: Microphone) -> tuple[int, int, int]:
        host_api = microphone["host_api_name"].casefold()
        if "wasapi" in host_api:
            host_priority = 0
        elif "directsound" in host_api:
            host_priority = 1
        elif "wdm" in host_api:
            host_priority = 2
        else:
            host_priority = 3
        return host_priority, -len(microphone["name"]), microphone["index"]


MicrophoneLevelCallback = Callable[[float], None]
MicrophoneErrorCallback = Callable[[], None]


class MicrophoneLevelMonitor:
    """Captura somente o nível do microfone selecionado para o visualizador."""

    def __init__(
        self,
        on_level: MicrophoneLevelCallback,
        *,
        input_device_index: int | None,
        sample_rate: int = 16000,
        on_error: MicrophoneErrorCallback | None = None,
    ) -> None:
        self.on_level = on_level
        self.on_error = on_error
        self.input_device_index = input_device_index
        self.sample_rate = sample_rate
        self._running = False

    async def start(self) -> None:
        self._running = True
        try:
            await asyncio.to_thread(self._capture)
        finally:
            self._running = False

    def stop(self) -> None:
        self._running = False

    def _capture(self) -> None:
        try:
            import sounddevice as sd

            device_index = self.input_device_index
            if device_index is None:
                default_devices = getattr(sd.default, "device", (-1, -1))
                device_index = int(default_devices[0])
            if device_index < 0:
                raise RuntimeError("Nenhum microfone está disponível.")

            device_info = sd.query_devices(device_index)
            if int(device_info["max_input_channels"]) <= 0:
                raise RuntimeError("O dispositivo selecionado não recebe áudio.")

            def on_audio(indata, frames, time_info, status) -> None:
                if not self._running:
                    return
                level = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
                self.on_level(min(1.0, level * 4.0))

            stream_options = {
                "channels": 1,
                "samplerate": int(device_info["default_samplerate"]),
                "callback": on_audio,
                "dtype": "float32",
                "blocksize": 1024,
                "device": device_index,
            }

            with sd.InputStream(**stream_options):
                while self._running:
                    time.sleep(0.1)
        except Exception:
            self.on_level(0.0)
            if self.on_error is not None:
                self.on_error()
