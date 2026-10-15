import unittest

import flet as ft

from ui.shared.components.form_controls import build_dropdown, build_text_field
from ui.theme.colors import BORDER, GREY_200, PASTEL_PURPLE, TEXT_PRIMARY


class InputStyleTests(unittest.TestCase):
    def test_disabled_inputs_use_grey_background_and_primary_text_and_border(self) -> None:
        text_field = build_text_field("Campo", "valor", disabled=True)
        dropdown = build_dropdown(
            "Seleção",
            "one",
            (("one", "Um"),),
            disabled=True,
        )

        for control in (text_field, dropdown):
            self.assertEqual(GREY_200, control.bgcolor)
            self.assertEqual(TEXT_PRIMARY, control.border_color)
            self.assertEqual(TEXT_PRIMARY, control.focused_border_color)
            self.assertEqual(TEXT_PRIMARY, control.text_style.color)
            self.assertEqual(14, control.text_style.size)
            self.assertEqual(14, control.label_style.size)
            self.assertEqual(14, control.hint_style.size)
            self.assertIsNone(control.helper_style.size)

    def test_enabled_inputs_keep_the_original_form_style(self) -> None:
        text_field = build_text_field("Campo", "valor")
        dropdown = build_dropdown(
            "Seleção",
            "one",
            (("one", "Um"),),
        )

        for control in (text_field, dropdown):
            self.assertIsNone(control.bgcolor)
            self.assertEqual(BORDER, control.border_color)
            self.assertEqual(PASTEL_PURPLE, control.focused_border_color)
            self.assertEqual(14, control.text_style.size)
            self.assertEqual(14, control.label_style.size)
            self.assertEqual(14, control.hint_style.size)
            self.assertIsNone(control.helper_style)

    def test_tall_text_field_starts_content_at_top_and_null_keeps_hint(self) -> None:
        field = build_text_field("Descrição", None, multiline=True)
        field.hint_text = "Informe a descrição."
        field.min_lines = 7
        field.max_lines = 7
        self.assertEqual("", field.value)
        self.assertEqual("Informe a descrição.", field.hint_text)
        self.assertEqual(ft.VerticalAlignment.START, field.text_vertical_align)
        self.assertEqual(ft.TextAlign.START, field.text_align)
        self.assertTrue(field.align_label_with_hint)


if __name__ == "__main__":
    unittest.main()
