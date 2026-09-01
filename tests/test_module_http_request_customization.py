import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base, enable_sqlite_foreign_keys
from database.models import Module, ModuleHttpRequest
from services.http_service import ModuleHttpRequestService
from services.module_registry_service import ModuleRegistryService
from services.module_service import get_module_detail
from tests.module_test_utils import (
    build_http_request,
    build_manifest,
    create_module_folder,
)


class ModuleHttpRequestCustomizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root = Path(self.temporary_directory.name)
        self.installed_root = root / "installed"
        self.installed_root.mkdir()
        self.module_folder = create_module_folder(
            self.installed_root,
            "http",
            build_manifest(
                "example.http",
                runtime=None,
                http_request=build_http_request(
                    params=[
                        {
                            "key": "search",
                            "value": "{{argument}}",
                            "description": "Busca original",
                            "enabled": True,
                        }
                    ]
                ),
            ),
            create_entrypoint=False,
        )
        self.engine = create_engine(f"sqlite:///{root / 'customization.db'}")
        self.addCleanup(self.engine.dispose)
        enable_sqlite_foreign_keys(self.engine)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.registry = ModuleRegistryService(
            self.installed_root,
            self.session_factory,
        )
        self.registry.sync()
        db = self.session_factory()
        try:
            self.module_id = db.query(Module).one().id
        finally:
            db.close()
        self.service = ModuleHttpRequestService(self.session_factory)

    def test_save_definition_persists_every_editable_http_field(self) -> None:
        saved = self.service.save_definition(
            self.module_id,
            method="post",
            url="https://custom.example.com/notes/{{argument}}",
            argument_enabled=True,
            argument="42",
            params_json=json.dumps(
                [
                    {
                        "key": "page",
                        "value": "2",
                        "description": "Página",
                        "enabled": True,
                    }
                ]
            ),
            authorization_json='{"type":"none"}',
            headers_json=json.dumps(
                [
                    {
                        "key": "Content-Type",
                        "value": "application/json",
                        "description": "Formato",
                        "enabled": True,
                    }
                ]
            ),
            body_json='{"mode":"raw_json","content":"{\\"id\\":\\"{{argument}}\\"}"}',
            scripts_json=(
                '{"pre_request":"console.log(\\"pre\\")",'
                '"post_response":"console.log(\\"post\\")"}'
            ),
        )

        self.assertEqual("POST", saved["method"])
        self.assertEqual("42", saved["argument"])
        self.assertEqual("raw_json", saved["body"]["mode"])
        self.assertEqual('console.log("pre")', saved["scripts"]["pre_request"])
        self.assertTrue(saved["is_customized"])

        detail = get_module_detail(self.module_id, self.session_factory)
        self.assertTrue(detail["is_available"])
        self.assertEqual(
            'console.log("post")',
            detail["http_request"]["scripts"]["post_response"],
        )

        db = self.session_factory()
        try:
            request = db.query(ModuleHttpRequest).one()
            self.assertEqual("POST", request.method)
            self.assertTrue(request.is_customized)
            self.assertIn("Content-Type", request.headers_json)
            self.assertIn("raw_json", request.body_json)
        finally:
            db.close()

    def test_registry_does_not_overwrite_saved_customization(self) -> None:
        self.service.save_definition(
            self.module_id,
            method="DELETE",
            url="https://custom.example.com/items/{{argument}}",
            argument_enabled=True,
            argument="9",
            params_json="[]",
            authorization_json='{"type":"none"}',
            headers_json="[]",
            body_json='{"mode":"none","content":""}',
            scripts_json='{"pre_request":"","post_response":""}',
        )

        self.registry.sync()

        db = self.session_factory()
        try:
            request = db.query(ModuleHttpRequest).one()
            self.assertEqual("DELETE", request.method)
            self.assertEqual("https://custom.example.com/items/{{argument}}", request.url)
            self.assertEqual("9", request.argument)
        finally:
            db.close()

    def test_reset_restores_manifest_and_preserves_last_argument(self) -> None:
        self.service.save_definition(
            self.module_id,
            method="DELETE",
            url="https://custom.example.com/items/{{argument}}",
            argument_enabled=False,
            argument="último argumento",
            params_json="[]",
            authorization_json='{"type":"none"}',
            headers_json="[]",
            body_json='{"mode":"none","content":""}',
            scripts_json='{"pre_request":"","post_response":""}',
        )

        restored = self.service.reset_definition_from_manifest(self.module_id)

        self.assertEqual("GET", restored["method"])
        self.assertEqual("https://api.example.com/items", restored["url"])
        self.assertTrue(restored["argument_enabled"])
        self.assertEqual("último argumento", restored["argument"])
        self.assertEqual("Busca original", restored["params"][0]["description"])
        self.assertFalse(restored["is_customized"])

    def test_sensitive_query_is_rejected_without_partial_save(self) -> None:
        with self.assertRaisesRegex(ValueError, "credencial"):
            self.service.save_definition(
                self.module_id,
                method="GET",
                url="https://custom.example.com/items?token=segredo",
                argument_enabled=False,
                argument="",
                params_json="[]",
                authorization_json='{"type":"none"}',
                headers_json="[]",
                body_json='{"mode":"none","content":""}',
                scripts_json='{"pre_request":"","post_response":""}',
            )

        db = self.session_factory()
        try:
            request = db.query(ModuleHttpRequest).one()
            self.assertEqual("https://api.example.com/items", request.url)
            self.assertFalse(request.is_customized)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
