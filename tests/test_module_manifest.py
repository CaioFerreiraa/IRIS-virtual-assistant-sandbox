import tempfile
import unittest
from pathlib import Path

from services.module_manifest import ManifestValidationError, parse_module_manifest
from tests.module_test_utils import build_manifest, create_module_folder


class ModuleManifestTests(unittest.TestCase):
    def parse(self, manifest: dict, **folder_options):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        installed_root = Path(temporary_directory.name)
        folder = create_module_folder(
            installed_root,
            "module",
            manifest,
            **folder_options,
        )
        return parse_module_manifest(manifest, folder)

    def test_valid_manifest(self) -> None:
        manifest = build_manifest(
            variables=[
                {
                    "key": "default_city",
                    "label": "Cidade padrão",
                    "description": "Cidade usada por padrão.",
                    "type": "text",
                    "required": True,
                    "user_editable": True,
                    "default_value": "",
                }
            ]
        )
        parsed = self.parse(manifest)
        self.assertEqual("weather", parsed.module_public_key)
        self.assertEqual("extension", parsed.icon)
        self.assertEqual("default_city", parsed.variables[0].key)

    def test_invalid_material_icon_name(self) -> None:
        manifest = build_manifest()
        manifest["module"]["icon"] = "Invalid icon"
        with self.assertRaisesRegex(ManifestValidationError, "Material Icons"):
            self.parse(manifest)

    def test_missing_icon_uses_compatibility_fallback(self) -> None:
        manifest = build_manifest()
        del manifest["module"]["icon"]

        self.assertEqual("extension", self.parse(manifest).icon)

    def test_missing_public_key(self) -> None:
        manifest = build_manifest()
        del manifest["module"]["module_public_key"]
        with self.assertRaisesRegex(ManifestValidationError, "module_public_key"):
            self.parse(manifest)

    def test_invalid_public_key_format(self) -> None:
        with self.assertRaisesRegex(ManifestValidationError, "letras minúsculas"):
            self.parse(build_manifest("Weather App"))

    def test_self_parent_reference(self) -> None:
        with self.assertRaisesRegex(ManifestValidationError, "si mesmo"):
            self.parse(build_manifest("weather", parent_public_key="weather"))

    def test_missing_readme(self) -> None:
        with self.assertRaisesRegex(ManifestValidationError, "README"):
            self.parse(build_manifest(), create_readme=False)

    def test_missing_entrypoint(self) -> None:
        with self.assertRaisesRegex(ManifestValidationError, "entry point"):
            self.parse(build_manifest(), create_entrypoint=False)

    def test_duplicate_variable_key(self) -> None:
        variable = {
            "key": "city",
            "label": "Cidade",
            "description": "Cidade.",
            "type": "text",
            "required": False,
            "user_editable": True,
            "default_value": "",
        }
        with self.assertRaisesRegex(ManifestValidationError, "mais de uma vez"):
            self.parse(build_manifest(variables=[variable, dict(variable)]))

    def test_unsupported_variable_type(self) -> None:
        variable = {
            "key": "limit",
            "label": "Limite",
            "description": "Limite.",
            "type": "number",
            "required": False,
            "user_editable": True,
            "default_value": None,
        }
        with self.assertRaisesRegex(ManifestValidationError, "não é suportado"):
            self.parse(build_manifest(variables=[variable]))

    def test_required_non_editable_variable_needs_default(self) -> None:
        variable = {
            "key": "api_version",
            "label": "Versão",
            "description": "Versão técnica.",
            "type": "text",
            "required": True,
            "user_editable": False,
            "default_value": "",
        }
        with self.assertRaisesRegex(ManifestValidationError, "valor padrão"):
            self.parse(build_manifest(variables=[variable]))

    def test_secret_variable_is_incompatible(self) -> None:
        variable = {
            "key": "api_token",
            "label": "Token",
            "description": "Não permitido.",
            "type": "text",
            "required": True,
            "user_editable": True,
            "default_value": "",
        }
        with self.assertRaisesRegex(ManifestValidationError, "sensível"):
            self.parse(build_manifest(variables=[variable]))


if __name__ == "__main__":
    unittest.main()
