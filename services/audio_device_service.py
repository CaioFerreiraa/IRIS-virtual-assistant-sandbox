from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AudioInputDevice:
    index: int
    name: str
    input_channels: int
    host_api: str = ""

    @property
    def label(self) -> str:
        source = f" — {self.host_api}" if self.host_api else ""
        return f"{self.name} (entrada {self.index}){source}"


class AudioDeviceService:
    """Enumera entradas do PortAudio sem expor sounddevice à camada visual."""

    def list_input_devices(self) -> list[AudioInputDevice]:
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            host_apis = sd.query_hostapis()
        except Exception as error:
            raise RuntimeError(
                "Não foi possível listar os microfones. Verifique o sounddevice e o PortAudio."
            ) from error

        input_devices: list[AudioInputDevice] = []
        for index, device in enumerate(devices):
            input_channels = int(device.get("max_input_channels", 0))
            if input_channels <= 0:
                continue
            host_api_index = int(device.get("hostapi", -1))
            host_api_name = ""
            if 0 <= host_api_index < len(host_apis):
                host_api_name = str(host_apis[host_api_index].get("name", ""))
            input_devices.append(
                AudioInputDevice(
                    index=index,
                    name=str(device.get("name", f"Microfone {index}")),
                    input_channels=input_channels,
                    host_api=host_api_name,
                )
            )
        return input_devices
