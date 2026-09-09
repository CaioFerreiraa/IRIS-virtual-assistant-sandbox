import unittest

import flet as ft

from ui.flet_app import build_route_loading


class RouteLoadingTests(unittest.TestCase):
    def test_route_loading_uses_iris_theme_and_clear_label(self) -> None:
        loading = build_route_loading()

        self.assertTrue(loading.expand)
        column = loading.content
        self.assertIsInstance(column, ft.Column)
        self.assertTrue(any(isinstance(control, ft.ProgressRing) for control in column.controls))
        self.assertTrue(
            any(
                isinstance(control, ft.Text) and control.value == "Carregando..."
                for control in column.controls
            )
        )


if __name__ == "__main__":
    unittest.main()
