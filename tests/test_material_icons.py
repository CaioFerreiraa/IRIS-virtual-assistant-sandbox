import unittest

from ui.shared.components.material_icons import material_icon
from ui.theme.fonts import FONT_ASSETS, MATERIAL_SYMBOLS_FONT


class MaterialIconsTests(unittest.TestCase):
    def test_material_icon_uses_registered_local_font(self) -> None:
        icon = material_icon("calendar_month", size=20, color="#123456")

        self.assertEqual("calendar_month", icon.value)
        self.assertEqual(MATERIAL_SYMBOLS_FONT, icon.font_family)
        self.assertEqual(20, icon.size)
        self.assertEqual("assets/fonts/MaterialSymbolsRounded.ttf", FONT_ASSETS[MATERIAL_SYMBOLS_FONT])

    def test_empty_icon_uses_safe_fallback(self) -> None:
        self.assertEqual("extension", material_icon("").value)


if __name__ == "__main__":
    unittest.main()
