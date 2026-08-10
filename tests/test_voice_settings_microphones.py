import asyncio
import unittest
from unittest.mock import Mock

import flet as ft

from ui.settings.voice_tab import VoiceSettingsTab


def build_microphone(microphone_id: str, index: int) -> dict:
    return {
        "id": microphone_id,
        "index": index,
        "name": f"Microfone {index}",
        "host_api": 0,
        "host_api_name": "Windows WASAPI",
        "channels": 1,
        "sample_rate": 16000,
    }


class VoiceSettingsMicrophoneTests(unittest.TestCase):
    def build_tab(self, *, saved_index: int | None, selected_id: str | None, loaded: bool):
        tab = VoiceSettingsTab.__new__(VoiceSettingsTab)
        tab.fields = {"input_device_index": ft.Dropdown()}
        tab.saved_microphone_index = saved_index
        tab.selected_microphone_id = selected_id
        tab._microphones_loaded = loaded
        tab._microphones_by_id = {}
        tab.selected_microphone_text = ft.Text()
        tab._is_mounted = Mock(return_value=False)
        tab._clear_saved_microphone = Mock()
        tab._update_microphone_controls = Mock()
        tab._start_level_monitor_for_selection = Mock()
        return tab

    def test_missing_saved_microphone_clears_selection(self) -> None:
        tab = self.build_tab(saved_index=16, selected_id=None, loaded=False)

        tab._apply_microphones([build_microphone("0:2:USB", 2)])

        self.assertIsNone(tab.selected_microphone_id)
        self.assertFalse(tab.fields["input_device_index"].disabled)
        tab._clear_saved_microphone.assert_called_once_with(show_toast=False)

    def test_available_unsaved_selection_is_preserved(self) -> None:
        tab = self.build_tab(saved_index=16, selected_id="0:2:USB", loaded=True)

        tab._apply_microphones([build_microphone("0:2:USB", 2)])

        self.assertEqual("0:2:USB", tab.selected_microphone_id)
        tab._clear_saved_microphone.assert_not_called()

    def test_empty_list_disables_field_and_clears_saved_microphone(self) -> None:
        tab = self.build_tab(saved_index=2, selected_id="0:2:USB", loaded=True)

        tab._apply_microphones([])

        self.assertIsNone(tab.selected_microphone_id)
        self.assertTrue(tab.fields["input_device_index"].disabled)
        self.assertEqual([], tab.fields["input_device_index"].options)
        tab._clear_saved_microphone.assert_called_once_with(show_toast=False)

    def test_visualizer_error_does_not_replace_selected_microphone(self) -> None:
        tab = self.build_tab(saved_index=None, selected_id="1:2:USB", loaded=True)
        tab.fields["input_device_index"].value = "1:2:USB"
        tab._stop_level_monitor = Mock()
        tab.audio_visualizer = Mock()
        tab.audio_visualizer.root = Mock()
        tab._is_mounted = Mock(return_value=False)

        asyncio.run(tab._apply_microphone_level_error())

        self.assertEqual("1:2:USB", tab.selected_microphone_id)
        self.assertEqual("1:2:USB", tab.fields["input_device_index"].value)
        tab._clear_saved_microphone.assert_not_called()

    def test_reload_button_dispatches_a_new_device_query(self) -> None:
        tab = self.build_tab(saved_index=None, selected_id=None, loaded=False)
        page = Mock()
        tab.root = Mock()
        tab.root.page = page
        tab._is_mounted = Mock(return_value=True)

        tab.on_reload_microphones()

        page.run_task.assert_called_once_with(tab._reload_microphones)

    def test_status_uses_selected_microphone(self) -> None:
        tab = self.build_tab(
            saved_index=None,
            selected_id="1:2:USB",
            loaded=True,
        )
        tab._microphones_by_id = {
            "1:2:USB": build_microphone("1:2:USB", 2)
        }

        tab._update_selected_microphone_status()

        self.assertEqual(
            "Microfone selecionado: Microfone 2.",
            tab.selected_microphone_text.value,
        )

    def test_status_uses_saved_microphone_when_selection_is_empty(self) -> None:
        tab = self.build_tab(
            saved_index=2,
            selected_id=None,
            loaded=True,
        )
        tab._microphones_by_id = {
            "1:2:USB": build_microphone("1:2:USB", 2)
        }

        tab._update_selected_microphone_status()

        self.assertEqual(
            "Microfone selecionado: Microfone 2.",
            tab.selected_microphone_text.value,
        )


if __name__ == "__main__":
    unittest.main()
