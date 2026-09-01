import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base, enable_sqlite_foreign_keys
from database.models import (
    Module,
    ModuleHttpRequest,
    ModuleVariableDefinition,
    ModuleVariableValue,
)
from services.module_registry_service import ModuleRegistryService
from tests.module_test_utils import (
    build_http_request,
    build_manifest,
    create_module_folder,
)


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

    def test_http_module_is_registered_once_with_correct_module_id(self) -> None:
        create_module_folder(
            self.installed_root,
            "http",
            build_manifest(
                "example.http",
                runtime=None,
                http_request=build_http_request(),
            ),
            create_entrypoint=False,
        )

        self.registry.sync()
        self.registry.sync()

        db = self.session_factory()
        try:
            module = db.query(Module).filter_by(
                module_public_key="example.http"
            ).one()
            requests = db.query(ModuleHttpRequest).all()
            self.assertEqual(1, len(requests))
            self.assertEqual(module.id, requests[0].module_id)
            self.assertEqual("GET", requests[0].method)
        finally:
            db.close()

    def test_http_resync_updates_definition_and_preserves_argument(self) -> None:
        folder = create_module_folder(
            self.installed_root,
            "http",
            build_manifest(
                "example.http",
                runtime=None,
                http_request=build_http_request(),
            ),
            create_entrypoint=False,
        )
        self.registry.sync()

        db = self.session_factory()
        try:
            request = db.query(ModuleHttpRequest).one()
            request.argument = "Campinas"
            db.commit()
        finally:
            db.close()

        updated_manifest = build_manifest(
            "example.http",
            runtime=None,
            http_request=build_http_request(
                method="POST",
                url="https://api.example.com/search",
                body={
                    "mode": "raw_json",
                    "content": '{"query":"{{argument}}"}',
                },
            ),
        )
        (folder / "module.json").write_text(
            json.dumps(updated_manifest, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )

        self.registry.sync()

        db = self.session_factory()
        try:
            request = db.query(ModuleHttpRequest).one()
            self.assertEqual("POST", request.method)
            self.assertEqual("https://api.example.com/search", request.url)
            self.assertIn("raw_json", request.body_json)
            self.assertEqual("Campinas", request.argument)
        finally:
            db.close()

    def test_http_resync_preserves_user_customized_definition(self) -> None:
        folder = create_module_folder(
            self.installed_root,
            "http-customized",
            build_manifest(
                "example.customized",
                runtime=None,
                http_request=build_http_request(),
            ),
            create_entrypoint=False,
        )
        self.registry.sync()

        db = self.session_factory()
        try:
            request = db.query(ModuleHttpRequest).one()
            request.method = "DELETE"
            request.url = "https://custom.example.com/items/7"
            request.argument = "7"
            request.is_customized = True
            db.commit()
        finally:
            db.close()

        updated_manifest = build_manifest(
            "example.customized",
            runtime=None,
            http_request=build_http_request(
                method="POST",
                url="https://manifest.example.com/items",
            ),
        )
        (folder / "module.json").write_text(
            json.dumps(updated_manifest, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )

        self.registry.sync()

        db = self.session_factory()
        try:
            request = db.query(ModuleHttpRequest).one()
            self.assertEqual("DELETE", request.method)
            self.assertEqual("https://custom.example.com/items/7", request.url)
            self.assertEqual("7", request.argument)
            self.assertTrue(request.is_customized)
        finally:
            db.close()

    def test_two_http_modules_receive_separate_requests(self) -> None:
        for public_key in ("example.first", "example.second"):
            create_module_folder(
                self.installed_root,
                public_key,
                build_manifest(
                    public_key,
                    runtime=None,
                    http_request=build_http_request(),
                ),
                create_entrypoint=False,
            )

        self.registry.sync()

        db = self.session_factory()
        try:
            requests = db.query(ModuleHttpRequest).order_by(
                ModuleHttpRequest.module_id
            ).all()
            self.assertEqual(2, len(requests))
            self.assertNotEqual(requests[0].module_id, requests[1].module_id)
        finally:
            db.close()

    def test_invalid_http_module_leaves_no_partial_record_and_does_not_block_others(self) -> None:
        create_module_folder(
            self.installed_root,
            "invalid-http",
            build_manifest(
                "example.invalid",
                runtime=None,
                http_request=build_http_request(method="TRACE"),
            ),
            create_entrypoint=False,
        )
        create_module_folder(
            self.installed_root,
            "valid-http",
            build_manifest(
                "example.valid",
                runtime=None,
                http_request=build_http_request(),
            ),
            create_entrypoint=False,
        )

        state = self.registry.sync()

        db = self.session_factory()
        try:
            self.assertEqual(
                0,
                db.query(Module).filter_by(
                    module_public_key="example.invalid"
                ).count(),
            )
            self.assertEqual(1, db.query(ModuleHttpRequest).count())
            self.assertEqual(
                "example.valid",
                db.query(ModuleHttpRequest).one().module.module_public_key,
            )
        finally:
            db.close()
        self.assertEqual(1, len(state.invalid_modules))
        self.assertEqual(1, len(state.synced_module_ids))

    def test_invalid_http_update_rolls_back_only_affected_module(self) -> None:
        folder = create_module_folder(
            self.installed_root,
            "http",
            build_manifest(
                "example.http",
                runtime=None,
                http_request=build_http_request(),
            ),
            create_entrypoint=False,
        )
        self.registry.sync()
        db = self.session_factory()
        try:
            request = db.query(ModuleHttpRequest).one()
            request.argument = "preservado"
            db.commit()
        finally:
            db.close()

        invalid_manifest = build_manifest(
            "example.http",
            runtime=None,
            http_request=build_http_request(method="TRACE"),
        )
        (folder / "module.json").write_text(
            json.dumps(invalid_manifest, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )

        state = self.registry.sync()

        db = self.session_factory()
        try:
            module = db.query(Module).filter_by(
                module_public_key="example.http"
            ).one()
            request = db.query(ModuleHttpRequest).filter_by(
                module_id=module.id
            ).one()
            self.assertFalse(module.is_available)
            self.assertIn("método HTTP", module.validation_error)
            self.assertEqual("GET", request.method)
            self.assertEqual("preservado", request.argument)
        finally:
            db.close()
        self.assertEqual(1, len(state.invalid_modules))


if __name__ == "__main__":
    unittest.main()
