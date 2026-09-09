import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import flet as ft

from ui.shared.components.toaster_handler import ToasterHandler


class ToasterHandlerTests(unittest.TestCase):
    def test_show_moves_notification_above_open_dialogs(self) -> None:
        page = SimpleNamespace(
            overlay=[],
            controls=[object()],
            update=Mock(),
            run_thread=Mock(),
        )
        toaster = ToasterHandler(page)
        toaster.mount()
        dialog = object()
        page.overlay.append(dialog)

        toaster.show_info("Mensagem")

        self.assertIs(page.overlay[0], toaster._toast_dialog)
        self.assertIsInstance(toaster._toast_dialog, ft.AlertDialog)
        self.assertFalse(toaster._toast_dialog.modal)
        self.assertIn(dialog, page.overlay)
        self.assertTrue(toaster._toast_dialog.open)
        page.update.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
