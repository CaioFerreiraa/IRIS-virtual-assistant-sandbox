from __future__ import annotations

import json


def get_connected_microphone_names() -> list[str]:
    """Enumera nomes atuais em uma instância isolada do PortAudio."""
    import pyaudio

    audio = pyaudio.PyAudio()
    try:
        host_apis = [
            audio.get_host_api_info_by_index(index)
            for index in range(audio.get_host_api_count())
        ]
        has_wasapi = any(
            "wasapi" in str(host_api.get("name", "")).casefold()
            for host_api in host_apis
        )
        microphones: list[str] = []
        for index in range(audio.get_device_count()):
            device = audio.get_device_info_by_index(index)
            if int(device.get("maxInputChannels", 0)) <= 0:
                continue

            host_api_index = int(device.get("hostApi", -1))
            host_api_name = (
                str(host_apis[host_api_index].get("name", ""))
                if 0 <= host_api_index < len(host_apis)
                else ""
            )
            if has_wasapi and "wasapi" not in host_api_name.casefold():
                continue
            microphones.append(str(device.get("name", "")).strip())
        return [name for name in microphones if name]
    finally:
        audio.terminate()


def main() -> None:
    print(json.dumps(get_connected_microphone_names()))


if __name__ == "__main__":
    main()
