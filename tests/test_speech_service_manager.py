import threading
import unittest
from unittest.mock import patch

from services.speech_service_manager import SpeechServiceManager
from services.voice_settings import VoiceSettings


class FakeSpeechService:
    started = threading.Event()

    def __init__(self, settings, on_event):
        self.settings = settings
        self.on_event = on_event
        self.stopped = False

    def start(self) -> None:
        self.started.set()

    def stop(self) -> None:
        self.stopped = True


class SpeechServiceManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeSpeechService.started.clear()

    def test_prepares_enabled_service_outside_calling_thread(self) -> None:
        manager = SpeechServiceManager()
        with patch(
            "services.speech_service_manager.FasterWhisperSpeechService",
            FakeSpeechService,
        ):
            manager.prepare(VoiceSettings(enabled=True))
            self.assertTrue(FakeSpeechService.started.wait(timeout=1))
        manager.shutdown()

    def test_disabled_configuration_does_not_start_backend(self) -> None:
        manager = SpeechServiceManager()
        with patch(
            "services.speech_service_manager.FasterWhisperSpeechService",
            FakeSpeechService,
        ):
            manager.prepare(VoiceSettings(enabled=False))
            self.assertFalse(FakeSpeechService.started.wait(timeout=0.1))
        manager.shutdown()


if __name__ == "__main__":
    unittest.main()
