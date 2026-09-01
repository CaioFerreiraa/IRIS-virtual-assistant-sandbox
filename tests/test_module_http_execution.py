import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from core.command_processor import CommandProcessor
from database.db import Base, enable_sqlite_foreign_keys
from database.models import Log, Module, ModuleHttpRequest
from repositories.module_repository import ModuleRepository


class ModuleHttpExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        database_path = Path(self.temporary_directory.name) / "http-execution.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        self.addCleanup(self.engine.dispose)
        enable_sqlite_foreign_keys(self.engine)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def _create_http_module(
        self,
        *,
        public_key: str = "example.http",
        method: str = "GET",
        url: str = "https://api.example.com/items/{{argument}}",
        argument_enabled: bool = True,
        params: list[dict] | None = None,
        headers: list[dict] | None = None,
        body: dict | None = None,
    ) -> int:
        db = self.session_factory()
        try:
            module = Module(
                module_public_key=public_key,
                name="Exemplo HTTP",
                call_name="http",
                is_executable=True,
                is_available=True,
            )
            db.add(module)
            db.flush()
            db.add(
                ModuleHttpRequest(
                    module_id=module.id,
                    method=method,
                    url=url,
                    argument_enabled=argument_enabled,
                    params_json=json.dumps(params or []),
                    authorization_json='{"type":"none"}',
                    headers_json=json.dumps(headers or []),
                    body_json=json.dumps(
                        body or {"mode": "none", "content": ""}
                    ),
                    scripts_json=(
                        '{"pre_request":"","post_response":""}'
                    ),
                )
            )
            db.commit()
            return int(module.id)
        finally:
            db.close()

    def _execute(self, module_id: int, argument: str | None = None) -> dict:
        db = self.session_factory()
        try:
            return CommandProcessor(
                ModuleRepository(db),
                self.session_factory,
            ).execute_module_id(module_id, argument)
        finally:
            db.close()

    def test_get_substitutes_argument_and_uses_http_service(self) -> None:
        module_id = self._create_http_module(
            params=[
                {
                    "key": "search",
                    "value": "{{argument}}",
                    "description": "Busca",
                    "enabled": True,
                }
            ],
            headers=[
                {
                    "key": "X-Search",
                    "value": "{{argument}}",
                    "description": "Busca",
                    "enabled": True,
                }
            ],
        )
        response = httpx.Response(
            200,
            json={"items": [1]},
            request=httpx.Request("GET", "https://api.example.com"),
        )

        with patch(
            "services.http_service.httpx.request",
            return_value=response,
        ) as mocked_request:
            result = self._execute(module_id, "Campinas")

        self.assertTrue(result["success"])
        self.assertEqual(200, result["status_code"])
        self.assertEqual({"items": [1]}, result["body"])
        self.assertEqual("GET", mocked_request.call_args.args[0])
        self.assertEqual(
            "https://api.example.com/items/Campinas",
            mocked_request.call_args.args[1],
        )
        self.assertEqual(
            {"search": "Campinas"},
            mocked_request.call_args.kwargs["params"],
        )
        self.assertEqual(
            {"X-Search": "Campinas"},
            mocked_request.call_args.kwargs["headers"],
        )

        db = self.session_factory()
        try:
            request = db.query(ModuleHttpRequest).filter_by(
                module_id=module_id
            ).one()
            log = db.query(Log).filter_by(module_id=module_id).one()
            self.assertEqual("Campinas", request.argument)
            self.assertIn("HTTP GET", log.message)
            self.assertIn("status 200", log.message)
            self.assertNotIn("api.example.com", log.message)
            self.assertNotIn("items", log.message)
        finally:
            db.close()

    def test_post_with_raw_json_sends_structured_body(self) -> None:
        module_id = self._create_http_module(
            method="POST",
            url="https://api.example.com/items",
            body={
                "mode": "raw_json",
                "content": '{"query":"{{argument}}","limit":2}',
            },
        )
        response = httpx.Response(
            201,
            json={"created": True},
            request=httpx.Request("POST", "https://api.example.com/items"),
        )

        with patch(
            "services.http_service.httpx.request",
            return_value=response,
        ) as mocked_request:
            result = self._execute(module_id, "teste")

        self.assertTrue(result["success"])
        self.assertEqual(
            {"query": "teste", "limit": 2},
            mocked_request.call_args.kwargs["json"],
        )
        self.assertNotIn("content", mocked_request.call_args.kwargs)

    def test_http_4xx_returns_structured_error_and_creates_error_log(self) -> None:
        module_id = self._create_http_module()
        response = httpx.Response(
            404,
            json={"error": "not found"},
            request=httpx.Request("GET", "https://api.example.com"),
        )

        with patch(
            "services.http_service.httpx.request",
            return_value=response,
        ):
            result = self._execute(module_id, "missing")

        self.assertFalse(result["success"])
        self.assertEqual(404, result["status_code"])
        self.assertEqual({"error": "not found"}, result["body"])
        db = self.session_factory()
        try:
            log = db.query(Log).filter_by(module_id=module_id).one()
            self.assertEqual("error", log.status)
            self.assertIn("status 404", log.message)
            self.assertNotIn("not found", log.message)
        finally:
            db.close()

    def test_timeout_and_connection_error_are_structured(self) -> None:
        timeout_module_id = self._create_http_module(public_key="example.timeout")
        connection_module_id = self._create_http_module(
            public_key="example.connection"
        )

        with patch(
            "services.http_service.httpx.request",
            side_effect=httpx.ReadTimeout("timeout"),
        ):
            timeout_result = self._execute(timeout_module_id, "x")
        with patch(
            "services.http_service.httpx.request",
            side_effect=httpx.ConnectError("refused"),
        ):
            connection_result = self._execute(connection_module_id, "x")

        self.assertFalse(timeout_result["success"])
        self.assertIn("30 segundos", timeout_result["message"])
        self.assertFalse(connection_result["success"])
        self.assertIn("conectar", connection_result["message"])

    def test_invalid_raw_json_is_rejected_without_network(self) -> None:
        module_id = self._create_http_module(
            method="POST",
            body={"mode": "raw_json", "content": "{invalid"},
        )

        with patch("services.http_service.httpx.request") as mocked_request:
            with self.assertRaisesRegex(ValueError, "JSON inválido"):
                self._execute(module_id, "x")

        mocked_request.assert_not_called()

    def test_credential_like_argument_is_not_saved_or_sent(self) -> None:
        module_id = self._create_http_module()

        with patch("services.http_service.httpx.request") as mocked_request:
            with self.assertRaisesRegex(ValueError, "credencial"):
                self._execute(module_id, "token=example-secret")

        mocked_request.assert_not_called()
        db = self.session_factory()
        try:
            request = db.query(ModuleHttpRequest).filter_by(
                module_id=module_id
            ).one()
            log = db.query(Log).filter_by(module_id=module_id).one()
            self.assertIsNone(request.argument)
            self.assertNotIn("example-secret", log.message)
        finally:
            db.close()

    def test_legacy_get_still_opens_browser_without_http_request(self) -> None:
        db = self.session_factory()
        try:
            module = Module(
                module_public_key="legacy.get",
                name="GET legado",
                call_name="legado",
                is_executable=True,
                is_available=True,
                request_method="GET",
                request_url="https://example.com/legacy",
            )
            db.add(module)
            db.commit()
            module_id = module.id
        finally:
            db.close()

        with patch("core.command_processor.webbrowser.open", return_value=True) as opened:
            with patch("services.http_service.httpx.request") as http_request:
                result = self._execute(module_id)

        self.assertTrue(result["success"])
        opened.assert_called_once_with("https://example.com/legacy")
        http_request.assert_not_called()

    def test_module_http_relationship_is_one_to_one(self) -> None:
        module_id = self._create_http_module()
        db = self.session_factory()
        try:
            module = db.query(Module).filter_by(id=module_id).one()
            self.assertIsNotNone(module.http_request)
            db.add(
                ModuleHttpRequest(
                    module_id=module_id,
                    method="GET",
                    url="https://example.com/other",
                )
            )
            with self.assertRaises(IntegrityError):
                db.commit()
        finally:
            db.rollback()
            db.close()


if __name__ == "__main__":
    unittest.main()
