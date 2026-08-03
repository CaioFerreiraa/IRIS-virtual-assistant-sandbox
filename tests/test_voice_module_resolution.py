import unittest

from ui.home.dropdowns import resolve_voice_module


MODULES = (
    {"path": "Abrir", "is_executable": False},
    {"path": "Abrir / App", "is_executable": True},
    {"path": "Abrir / Web / Verde", "is_executable": True},
)


class VoiceModuleResolutionTests(unittest.TestCase):
    def test_selects_executable_prefix_and_keeps_argument(self) -> None:
        self.assertEqual(
            ("Abrir / App", "Spotify"),
            resolve_voice_module("abrir app Spotify", MODULES),
        )

    def test_prefers_longest_executable_path(self) -> None:
        self.assertEqual(
            ("Abrir / Web / Verde", ""),
            resolve_voice_module("abrir web verde", MODULES),
        )

    def test_does_not_resolve_organizational_module(self) -> None:
        self.assertIsNone(resolve_voice_module("abrir", MODULES))


if __name__ == "__main__":
    unittest.main()
