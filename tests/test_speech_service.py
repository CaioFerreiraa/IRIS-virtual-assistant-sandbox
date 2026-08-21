import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

from services.speech_service import (
    FasterWhisperSpeechService,
    NoInputDeviceError,
    SpeechEventKind,
    SpeechService,
)
from services.voice_settings import VoiceSettings


class StubSpeechService(SpeechService):
    def _run(self) -> None:
        return


class SpeechServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events = []
        self.service = StubSpeechService(VoiceSettings(), self.events.append)

    def test_ignores_speech_until_wake_word(self) -> None:
        self.service.process_transcription("abrir aplicativo", is_partial=True)
        self.assertEqual([], self.events)

    def test_publishes_raw_transcription_for_microphone_diagnostics(self) -> None:
        self.service._emit_transcription("fala de teste", source="faster_whisper", is_partial=False)

        self.assertEqual(SpeechEventKind.TRANSCRIPTION, self.events[-1].kind)
        self.assertEqual("fala de teste", self.events[-1].text)
        self.assertEqual("faster_whisper", self.events[-1].source)

    def test_publishes_normalized_audio_level(self) -> None:
        self.service._emit_audio_level(0.025, force=True)

        self.assertEqual(SpeechEventKind.AUDIO_LEVEL, self.events[-1].kind)
        self.assertAlmostEqual(0.5, self.events[-1].audio_level)

    def test_ignores_wake_word_when_command_is_disabled_for_route(self) -> None:
        self.service.set_command_enabled(False)
        self.service.process_transcription("Iris abrir aplicativo", is_partial=False)

        self.assertEqual([], self.events)

    def test_wake_word_is_removed_from_progressive_text(self) -> None:
        self.service.process_transcription("Íris abrir", is_partial=True)
        self.service.process_transcription("Íris abrir app", is_partial=True)

        self.assertEqual(SpeechEventKind.ACTIVATED, self.events[0].kind)
        self.assertEqual("abrir", self.events[1].text)
        self.assertEqual("abrir app", self.events[2].text)
        self.assertNotIn("Íris", self.events[2].text)

    def test_send_word_submits_last_command_and_deactivates(self) -> None:
        self.service.process_transcription("Iris abrir app Spotify", is_partial=False)
        self.service.process_transcription("enviar", is_partial=False)

        final_event = self.events[-2]
        self.assertEqual(SpeechEventKind.FINAL, final_event.kind)
        self.assertEqual("abrir app Spotify", final_event.text)
        self.assertTrue(final_event.should_submit)
        self.assertEqual(SpeechEventKind.DEACTIVATED, self.events[-1].kind)

    def test_partial_send_word_does_not_execute_while_user_is_speaking(self) -> None:
        self.service.process_transcription("Iris abrir app enviar", is_partial=True)

        self.assertEqual(SpeechEventKind.PARTIAL, self.events[-1].kind)
        self.assertFalse(self.events[-1].should_submit)
        self.assertNotIn(SpeechEventKind.DEACTIVATED, [event.kind for event in self.events])

    def test_keeps_previous_final_text_when_command_continues_after_pause(self) -> None:
        self.service.process_transcription("Iris abrir app", is_partial=False)
        self.service.process_transcription("Spotify", is_partial=False)

        self.assertEqual("abrir app Spotify", self.events[-1].text)

    def test_fixed_prompt_is_always_combined_with_user_context(self) -> None:
        settings = VoiceSettings(proper_names="Caio", context="Abrir aplicativos", hotwords="Spotify")
        prompt = settings.build_initial_prompt()

        self.assertIn("Íris", prompt)
        self.assertIn("Caio", prompt)
        self.assertIn("Abrir aplicativos", prompt)
        self.assertIn("Spotify", prompt)

    def test_basic_mode_reports_capture_around_final_transcription(self) -> None:
        events = []
        service = FasterWhisperSpeechService(
            VoiceSettings(silence_duration=0.2),
            events.append,
        )

        class FakeInputStream:
            def __init__(self, **options):
                self.callback = options["callback"]

            def __enter__(self):
                speaking = np.full(1600, 0.05, dtype=np.float32)
                silence = np.zeros(1600, dtype=np.float32)
                self.callback(speaking, len(speaking), None, None)
                self.callback(silence, len(silence), None, None)
                self.callback(silence, len(silence), None, None)
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

        class FakeWhisperModel:
            def __init__(self, *args, **kwargs):
                pass

            def transcribe(self, audio, **kwargs):
                service._stop_event.set()
                return [types.SimpleNamespace(text=" Iris abrir aplicativo")], None

        fake_sounddevice = types.SimpleNamespace(
            default=types.SimpleNamespace(device=[1, 1]),
            query_devices=lambda index: {"max_input_channels": 1},
            InputStream=FakeInputStream,
        )
        fake_faster_whisper = types.SimpleNamespace(WhisperModel=FakeWhisperModel)

        with patch.dict(
            sys.modules,
            {
                "sounddevice": fake_sounddevice,
                "faster_whisper": fake_faster_whisper,
            },
        ):
            service._run()

        event_kinds = [event.kind for event in events]
        self.assertIn(SpeechEventKind.CAPTURE_STARTED, event_kinds)
        self.assertIn(SpeechEventKind.CAPTURE_FINISHED, event_kinds)
        self.assertLess(
            event_kinds.index(SpeechEventKind.CAPTURE_STARTED),
            event_kinds.index(SpeechEventKind.ACTIVATED),
        )
        self.assertLess(
            event_kinds.index(SpeechEventKind.FINAL),
            event_kinds.index(SpeechEventKind.CAPTURE_FINISHED),
        )

    def test_invalid_saved_microphone_falls_back_to_system_default(self) -> None:
        fake_sounddevice = types.SimpleNamespace(
            default=types.SimpleNamespace(device=[-1, 1]),
            query_devices=lambda index: (_ for _ in ()).throw(RuntimeError("device not found")),
        )
        service = FasterWhisperSpeechService(VoiceSettings(input_device_index=16))

        with patch.dict(sys.modules, {"sounddevice": fake_sounddevice}):
            with self.assertRaises(NoInputDeviceError):
                service._resolve_input_device_index()


if __name__ == "__main__":
    unittest.main()
