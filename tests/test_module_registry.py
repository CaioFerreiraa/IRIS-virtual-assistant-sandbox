import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base, enable_sqlite_foreign_keys
from database.models import Module, ModuleVariableDefinition, ModuleVariableValue
from services.module_registry_service import ModuleRegistryService
from tests.module_test_utils import build_manifest, create_module_folder


class ModuleRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root = Path(self.temporary_directory.name)
        self.installed_root = root / "installed"
        self.installed_root.mkdir()
        self.engine = create_engine(f"sqlite:///{root / 'iris-test.db'}")
        self.addCleanup(self.engine.dispose)
        enable_sqlite_foreign_keys(self.engine)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.registry = ModuleRegistryService(
            self.installed_root,
            self.session_factory,
        )

    def test_valid_module_is_synchronized(self) -> None:
        create_module_folder(self.installed_root, "weather", build_manifest())
        state = self.registry.sync()

        db = self.session_factory()
        try:
            module = db.query(Module).filter(Module.module_public_key == "weather").one()
            self.assertTrue(module.is_available)
            self.assertEqual("PYTHON", module.request_method)
            self.assertEqual("extension", module.icon)
        finally:
            db.close()
        self.assertEqual(1, len(state.synced_module_ids))
        self.assertIn("Módulo de teste", state.readme_contents[module.id])

    def test_invalid_json_and_missing_manifest_are_isolated(self) -> None:
        invalid_json_folder = self.installed_root / "invalid-json"
        invalid_json_folder.mkdir()
        (invalid_json_folder / "module.json").write_text("{invalid", encoding="utf-8")
        missing_manifest_folder = self.installed_root / "missing-manifest"
        missing_manifest_folder.mkdir()
        create_module_folder(self.installed_root, "valid", build_manifest("valid"))

        state = self.registry.sync()

        self.assertEqual(2, len(state.invalid_modules))
        self.assertEqual(1, len(state.synced_module_ids))
        self.assertTrue((invalid_json_folder / "module.log").is_file())
        self.assertTrue((missing_manifest_folder / "module.log").is_file())

    def test_duplicate_public_key_does_not_create_record(self) -> None:
        create_module_folder(self.installed_root, "first", build_manifest("duplicate"))
        create_module_folder(self.installed_root, "second", build_manifest("duplicate"))

        state = self.registry.sync()

        db = self.session_factory()
        try:
            count = db.query(Module).filter(Module.module_public_key == "duplicate").count()
        finally:
            db.close()
        self.assertEqual(0, count)
        self.assertEqual(2, len(state.invalid_modules))

    def test_missing_parent_is_invalid(self) -> None:
        create_module_folder(
            self.installed_root,
            "child",
            build_manifest("child", parent_public_key="missing"),
        )
        state = self.registry.sync()
        self.assertIn("não foi encontrado", state.invalid_modules[0].message)
        self.assertEqual("missing", state.invalid_modules[0].parent_public_key)

    def test_indirect_cycle_is_invalid(self) -> None:
        create_module_folder(
            self.installed_root,
            "first",
            build_manifest("first", parent_public_key="second", runtime=None),
            create_entrypoint=False,
        )
        create_module_folder(
            self.installed_root,
            "second",
            build_manifest("second", parent_public_key="first", runtime=None),
            create_entrypoint=False,
        )
        state = self.registry.sync()
        self.assertEqual(2, len(state.invalid_modules))
        self.assertTrue(all("ciclo" in item.message for item in state.invalid_modules))

    def test_import_failure_does_not_interrupt_valid_module(self) -> None:
        create_module_folder(
            self.installed_root,
            "broken",
            build_manifest("broken"),
            main_source="raise RuntimeError('import failed')\n",
        )
        create_module_folder(self.installed_root, "valid", build_manifest("valid"))

        state = self.registry.sync()

        self.assertEqual(1, len(state.invalid_modules))
        self.assertEqual(1, len(state.synced_module_ids))
        self.assertIn("import failed", state.invalid_modules[0].message)

    def test_module_log_uses_append(self) -> None:
        folder = self.installed_root / "missing"
        folder.mkdir()
        self.registry.sync()
        self.registry.sync()
        content = (folder / "module.log").read_text(encoding="utf-8")
        self.assertGreaterEqual(content.count("Etapa:"), 2)
        self.assertIn("Traceback:", content)

    def test_sync_preserves_custom_call_name_and_user_value(self) -> None:
        variable = {
            "key": "default_city",
            "label": "Cidade",
            "description": "Cidade padrão.",
            "type": "text",
            "required": True,
            "user_editable": True,
            "default_value": "Recife",
        }
        folder = create_module_folder(
            self.installed_root,
            "weather",
            build_manifest(variables=[variable]),
        )
        self.registry.sync()

        db = self.session_factory()
        try:
            module = db.query(Module).filter(Module.module_public_key == "weather").one()
            module.custom_call_name = "tempo"
            definition = db.query(ModuleVariableDefinition).filter_by(module_id=module.id).one()
            db.add(
                ModuleVariableValue(
                    variable_definition_id=definition.id,
                    value_text="Fortaleza",
                )
            )
            db.commit()
        finally:
            db.close()

        updated_manifest = build_manifest(
            variables=[{**variable, "label": "Cidade preferida", "default_value": "Natal"}]
        )
        (folder / "module.json").write_text(
            json.dumps(updated_manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        self.registry.sync()

        db = self.session_factory()
        try:
            module = db.query(Module).filter(Module.module_public_key == "weather").one()
            definition = db.query(ModuleVariableDefinition).filter_by(module_id=module.id).one()
            value = db.query(ModuleVariableValue).filter_by(variable_definition_id=definition.id).one()
            self.assertEqual("tempo", module.custom_call_name)
            self.assertEqual("Cidade preferida", definition.label)
            self.assertEqual("Fortaleza", value.value_text)
        finally:
            db.close()

    def test_registered_module_becomes_unavailable_after_import_failure(self) -> None:
        folder = create_module_folder(self.installed_root, "weather", build_manifest())
        self.registry.sync()
        (folder / "main.py").write_text("raise RuntimeError('broken')\n", encoding="utf-8")

        self.registry.sync()

        db = self.session_factory()
        try:
            module = db.query(Module).filter(Module.module_public_key == "weather").one()
            self.assertFalse(module.is_available)
            self.assertIn("broken", module.validation_error)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
