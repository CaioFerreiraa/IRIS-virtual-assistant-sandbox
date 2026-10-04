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
        self.command_enabled = True
        self.classify_command = None

    def start(self) -> None:
        self.started.set()

    def stop(self) -> None:
        self.stopped = True

    def set_command_enabled(self, enabled: bool) -> None:
        self.command_enabled = enabled

    def set_command_classifier(self, classify_command) -> None:
        self.classify_command = classify_command

    def deactivate_command(self) -> None:
        return


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

    def test_route_command_state_is_applied_before_backend_starts(self) -> None:
        manager = SpeechServiceManager()
        manager.set_command_enabled(False)
        with patch(
            "services.speech_service_manager.FasterWhisperSpeechService",
            FakeSpeechService,
        ):
            manager.prepare(VoiceSettings(enabled=True))
            self.assertTrue(FakeSpeechService.started.wait(timeout=1))
            self.assertIsNotNone(manager._service)
            self.assertFalse(manager._service.command_enabled)
        manager.shutdown()

    def test_classifier_is_given_to_backend_before_start(self) -> None:
        manager = SpeechServiceManager()
        classify = lambda _text: None
        manager.set_command_classifier(classify)
        with patch(
            "services.speech_service_manager.FasterWhisperSpeechService",
            FakeSpeechService,
        ):
            manager.prepare(VoiceSettings(enabled=True))
            self.assertTrue(FakeSpeechService.started.wait(timeout=1))
            self.assertIs(manager._service.classify_command, classify)
        manager.shutdown()


if __name__ == "__main__":
    unittest.main()
