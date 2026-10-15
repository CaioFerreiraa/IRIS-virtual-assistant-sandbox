import unittest

import flet as ft

from ui.shared.components.vault_reference_field import (
    INVALID_REFERENCE_BACKGROUND,
    VaultReferenceField,
    build_placeholder_text,
    matching_vault_names,
    sync_reference_field_style,
)
from ui.theme.colors import PASTEL_GREY_BLUE, SURFACE


class VaultReferenceUiTests(unittest.TestCase):
    def test_argument_placeholder_uses_pastel_grey_blue(self) -> None:
        field = ft.TextField(value="prefixo {{argument}} sufixo")
        sync_reference_field_style(field, ())
        label = build_placeholder_text("Use {{argument}} aqui")
        self.assertEqual(PASTEL_GREY_BLUE, field.bgcolor)
        highlighted = [span for span in label.spans if span.text == "{{argument}}"]
        self.assertEqual(PASTEL_GREY_BLUE, highlighted[0].style.bgcolor)

    def test_vk_prefix_lists_matching_available_keys(self) -> None:
        self.assertEqual(
            ("NOTES_ACCESS_KEY",),
            matching_vault_names("token={{vk.NOT", ("OTHER", "NOTES_ACCESS_KEY")),
        )

    def test_selecting_suggestion_inserts_complete_reference(self) -> None:
        field = ft.TextField(value="token={{vk.NOT")
        reference_field = VaultReferenceField(field, ("NOTES_ACCESS_KEY",))
        self.assertTrue(reference_field.suggestions.visible)
        reference_field._select("NOTES_ACCESS_KEY")
        self.assertEqual("token={{vk.NOTES_ACCESS_KEY}}", field.value)
        self.assertFalse(reference_field.suggestions.visible)
        self.assertEqual(SURFACE, field.bgcolor)

    def test_unknown_or_unconfigured_key_uses_red_background(self) -> None:
        for value in ("{{vk.MISSING}}", "{{OLD_STYLE}}", "{{vk.UNKNOWN"):
            with self.subTest(value=value):
                field = ft.TextField(value=value)
                sync_reference_field_style(field, ("NOTES_ACCESS_KEY",))
                self.assertEqual(INVALID_REFERENCE_BACKGROUND, field.bgcolor)


if __name__ == "__main__":
    unittest.main()
