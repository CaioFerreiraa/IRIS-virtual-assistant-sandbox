import sys
import unittest
from unittest.mock import patch

from services.audio_device_service import AudioDeviceService, MicrophoneLevelMonitor


class FakeSoundDevice:
    def __init__(self, devices, host_apis=None):
        self._devices = devices
        self._host_apis = host_apis or ["MME", "Windows DirectSound", "Windows WASAPI"]

    def query_devices(self):
        return self._devices

    def query_hostapis(self):
        return [{"name": host_api} for host_api in self._host_apis]


class AudioDeviceServiceTests(unittest.TestCase):
    @patch.object(
        AudioDeviceService,
        "_probe_connected_microphone_names",
        return_value=["Microfone USB"],
    )
    def test_keeps_one_entry_for_each_microphone_and_ignores_virtual_inputs(
        self,
        connected_microphones,
    ) -> None:
        sounddevice = FakeSoundDevice(
            [
                {"name": "Saída de áudio", "max_input_channels": 0, "hostapi": 0, "default_samplerate": 44100},
                {"name": "Microfone USB", "max_input_channels": 1, "hostapi": 1, "default_samplerate": 16000},
                {"name": "Microfone USB", "max_input_channels": 2, "hostapi": 2, "default_samplerate": 48000},
                {"name": "Driver de captura de som primário", "max_input_channels": 2, "hostapi": 1, "default_samplerate": 48000},
            ]
        )

        with patch.dict(sys.modules, {"sounddevice": sounddevice}):
            microphones = AudioDeviceService.get_microphones()

        self.assertEqual(1, len(microphones))
        self.assertEqual("2:2:Microfone USB", microphones[0]["id"])

    @patch.object(
        AudioDeviceService,
        "_probe_connected_microphone_names",
        return_value=[
            "Microfone do Headset (2- Plantronics Blackwire 3220 Series)"
        ],
    )
    def test_groups_windows_instance_names(self, connected_microphones) -> None:
        sounddevice = FakeSoundDevice(
            [
                {"name": "Microfone do Headset (2- Plantronics Blackwire 3220 Series)", "max_input_channels": 1, "hostapi": 0, "default_samplerate": 44100},
                {"name": "Microfone do Headset ( Plantronics Blackwire 3220 Series)", "max_input_channels": 1, "hostapi": 1, "default_samplerate": 44100},
            ],
            host_apis=["MME", "Windows WASAPI"],
        )

        with patch.dict(sys.modules, {"sounddevice": sounddevice}):
            microphones = AudioDeviceService.get_microphones()

        self.assertEqual(1, len(microphones))
        self.assertEqual(1, microphones[0]["host_api"])

    def test_returns_empty_list_when_no_input_device_exists(self) -> None:
        sounddevice = FakeSoundDevice(
            [{"name": "Saída", "max_input_channels": 0, "hostapi": 0, "default_samplerate": 44100}]
        )

        with patch.dict(sys.modules, {"sounddevice": sounddevice}):
            microphones = AudioDeviceService.get_microphones()

        self.assertEqual([], microphones)

    def test_windows_ignores_legacy_connectors_without_active_wasapi_endpoint(self) -> None:
        sounddevice = FakeSoundDevice(
            [
                {
                    "name": "Microfone (Realtek HD Audio Mic input)",
                    "max_input_channels": 2,
                    "hostapi": 2,
                    "default_samplerate": 44100,
                }
            ],
            host_apis=["MME", "Windows WASAPI", "Windows WDM-KS"],
        )

        with patch.dict(sys.modules, {"sounddevice": sounddevice}):
            microphones = AudioDeviceService.get_microphones()

        self.assertEqual([], microphones)

    def test_level_monitor_reports_missing_default_without_opening_stream(self) -> None:
        class NoInputSoundDevice:
            class default:
                device = (-1, -1)

        levels = []
        errors = []
        monitor = MicrophoneLevelMonitor(
            levels.append,
            input_device_index=None,
            on_error=lambda: errors.append(True),
        )
        monitor._running = True

        with patch.dict(sys.modules, {"sounddevice": NoInputSoundDevice()}):
            monitor._capture()

        self.assertEqual([0.0], levels)
        self.assertEqual([True], errors)


if __name__ == "__main__":
    unittest.main()
