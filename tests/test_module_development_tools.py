from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from modules.cli import main
from services.module_development_service import (
    ModuleDevelopmentService,
    ModuleScaffoldError,
)
from tests.module_test_utils import build_manifest, create_module_folder


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ModuleDevelopmentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.service = ModuleDevelopmentService(
            installed_modules_dir=self.root / "installed",
            examples_dir=PROJECT_ROOT / "modules" / "examples",
        )

    def test_static_validation_does_not_import_python_entrypoint(self) -> None:
        folder = create_module_folder(
            self.root,
            "unsafe",
            build_manifest("example.unsafe"),
            main_source='raise RuntimeError("não deve importar")\n',
        )

        report = self.service.validate_module(folder)

        self.assertTrue(report.is_valid)
        self.assertFalse(report.checked_runtime)

    def test_runtime_check_reports_import_failure(self) -> None:
        folder = create_module_folder(
            self.root,
            "broken",
            build_manifest("example.broken"),
            main_source='raise RuntimeError("falha controlada")\n',
        )

        report = self.service.validate_module(folder, check_runtime=True)

        self.assertFalse(report.is_valid)
        self.assertEqual(report.stage, "importação")
        self.assertEqual(report.module_public_key, "example.broken")
        self.assertIn("falha controlada", report.message)

    def test_runtime_check_reports_missing_execution_function(self) -> None:
        folder = create_module_folder(
            self.root,
            "missing_contract",
            build_manifest("example.missing"),
            main_source="VALUE = 1\n",
        )

        report = self.service.validate_module(folder, check_runtime=True)

        self.assertFalse(report.is_valid)
        self.assertEqual(report.stage, "configuração")
        self.assertIn("execute, run ou main", report.message)

    def test_create_python_module_customizes_and_validates_template(self) -> None:
        target = self.service.create_module(
            "community.hello-world",
            "Olá comunidade",
            kind="python",
        )

        manifest = json.loads((target / "module.json").read_text(encoding="utf-8"))
        report = self.service.validate_module(target, check_runtime=True)

        self.assertEqual(target, self.root / "installed" / "community_hello_world")
        self.assertEqual(manifest["module"]["module_public_key"], "community.hello-world")
        self.assertEqual(manifest["module"]["name"], "Olá comunidade")
        self.assertEqual(manifest["module"]["call_name"], "hello world")
        self.assertIn("# Olá comunidade", (target / "README.md").read_text(encoding="utf-8"))
        self.assertTrue(report.is_valid)

    def test_create_http_module_validates_without_python_runtime(self) -> None:
        target = self.service.create_module(
            "community.lookup",
            "Consulta comunitária",
            kind="http",
        )

        report = self.service.validate_module(target, check_runtime=True)

        self.assertTrue(report.is_valid)
        self.assertIsNone(report.runtime_type)
        self.assertTrue(report.is_executable)
        self.assertFalse((target / "main.py").exists())

    def test_create_module_does_not_replace_existing_destination(self) -> None:
        target = self.root / "existing"
        target.mkdir()
        marker = target / "keep.txt"
        marker.write_text("preservar", encoding="utf-8")

        with self.assertRaisesRegex(ModuleScaffoldError, "não foi alterado"):
            self.service.create_module(
                "community.existing",
                "Existente",
                output_path=target,
            )

        self.assertEqual(marker.read_text(encoding="utf-8"), "preservar")

    def test_create_module_rejects_existing_public_key_in_another_folder(self) -> None:
        first_target = self.service.create_module(
            "community.unique",
            "Primeiro",
        )

        with self.assertRaisesRegex(ModuleScaffoldError, "já existe"):
            self.service.create_module(
                "community.unique",
                "Segundo",
                output_path=self.root / "another",
            )

        self.assertTrue(first_target.is_dir())
        self.assertFalse((self.root / "another").exists())

    def test_list_installed_modules_is_sorted_and_keeps_invalid_folders(self) -> None:
        installed = self.root / "installed"
        create_module_folder(
            installed,
            "z_valid",
            build_manifest("community.valid"),
        )
        (installed / "A_invalid").mkdir(parents=True)

        reports = self.service.list_installed_modules()

        self.assertEqual(
            ["A_invalid", "z_valid"],
            [report.folder.name for report in reports],
        )
        self.assertFalse(reports[0].is_valid)
        self.assertTrue(reports[1].is_valid)

    def test_json_schema_is_valid_json(self) -> None:
        schema = json.loads(
            (PROJECT_ROOT / "modules" / "module.schema.json").read_text(encoding="utf-8")
        )

        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["properties"]["schema_version"]["const"], 1)


class ModuleCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    def test_new_and_check_commands_complete_the_happy_path(self) -> None:
        target = self.root / "hello"
        output = StringIO()
        with redirect_stdout(output):
            create_exit_code = main(
                [
                    "new",
                    "community.hello",
                    "--name",
                    "Olá",
                    "--output",
                    str(target),
                ]
            )
            check_exit_code = main(["check", str(target)])

        self.assertEqual(create_exit_code, 0)
        self.assertEqual(check_exit_code, 0)
        self.assertIn("Módulo criado", output.getvalue())
        self.assertIn("Válido", output.getvalue())

    def test_validate_json_returns_nonzero_for_invalid_module(self) -> None:
        target = self.root / "invalid"
        target.mkdir()
        output = StringIO()

        with redirect_stdout(output), redirect_stderr(StringIO()):
            exit_code = main(["validate", str(target), "--json"])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["stage"], "validação do manifesto")


if __name__ == "__main__":
    unittest.main()
