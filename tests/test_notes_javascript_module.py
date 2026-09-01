from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from unittest.mock import MagicMock, Mock, mock_open, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.command_processor import CommandProcessor
from database.db import Base, enable_sqlite_foreign_keys
from database.models import Log, Module, ModuleHttpRequest
from repositories.module_repository import ModuleRepository
from services.module_loader import load_python_entrypoint
from services.module_manifest import parse_module_manifest
from services.module_registry_service import ModuleRegistryService
from services.module_runtime_service import ModuleRuntimeManager
from services.module_service import get_module_detail
from ui.modules.views.module_view_state import ModuleViewState


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALLED_MODULES_ROOT = PROJECT_ROOT / "modules" / "installed"
NOTES_FOLDERS = (
    "notes_javascript",
    "notes_javascript_open",
    "notes_javascript_create",
    "notes_javascript_edit",
    "notes_javascript_delete",
)
NOTES_PUBLIC_KEYS = (
    "notes.javascript",
    "notes.javascript.open",
    "notes.javascript.create",
    "notes.javascript.edit",
    "notes.javascript.delete",
)


def load_notes_entrypoint(folder_name: str, public_key: str):
    return load_python_entrypoint(
        INSTALLED_MODULES_ROOT / folder_name / "main.py",
        public_key,
    )


class NotesManifestAndRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        database_path = Path(self.temporary_directory.name) / "notes.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        self.addCleanup(self.engine.dispose)
        enable_sqlite_foreign_keys(self.engine)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.registry = ModuleRegistryService(
            INSTALLED_MODULES_ROOT,
            self.session_factory,
        )

    def test_all_five_manifests_are_valid(self) -> None:
        manifests = []
        for folder_name in NOTES_FOLDERS:
            folder = INSTALLED_MODULES_ROOT / folder_name
            manifest_data = json.loads(
                (folder / "module.json").read_text(encoding="utf-8")
            )
            manifests.append(parse_module_manifest(manifest_data, folder))

        self.assertEqual(NOTES_PUBLIC_KEYS, tuple(
            manifest.module_public_key for manifest in manifests
        ))

    def test_registry_creates_hierarchy_and_expected_execution_types(self) -> None:
        state = self.registry.sync()
        self.assertEqual((), state.invalid_modules)

        db = self.session_factory()
        try:
            modules = {
                module.module_public_key: module
                for module in db.query(Module)
                .filter(Module.module_public_key.in_(NOTES_PUBLIC_KEYS))
                .all()
            }
            root = modules["notes.javascript"]
            self.assertEqual(5, len(modules))
            self.assertIsNone(root.parent_module_id)
            self.assertFalse(root.is_executable)
            self.assertTrue(root.supports_auto_start)
            self.assertFalse(root.auto_start_enabled)

            for child_key in NOTES_PUBLIC_KEYS[1:]:
                child = modules[child_key]
                self.assertEqual(root.id, child.parent_module_id)
                self.assertTrue(child.is_executable)
                self.assertFalse(child.supports_auto_start)

            self.assertEqual("PYTHON", modules["notes.javascript.open"].request_method)
            for child_key in NOTES_PUBLIC_KEYS[2:]:
                self.assertIsNotNone(modules[child_key].http_request)
        finally:
            db.close()

    def test_http_definitions_are_synchronized_exactly(self) -> None:
        self.registry.sync()
        db = self.session_factory()
        try:
            definitions = {
                request.module.module_public_key: request
                for request in db.query(ModuleHttpRequest).join(Module).filter(
                    Module.module_public_key.in_(NOTES_PUBLIC_KEYS)
                )
            }
            self.assertEqual(
                {
                    "notes.javascript.create",
                    "notes.javascript.edit",
                    "notes.javascript.delete",
                },
                set(definitions),
            )

            create = definitions["notes.javascript.create"]
            self.assertEqual("POST", create.method)
            self.assertEqual("http://127.0.0.1:8765/api/notes", create.url)
            self.assertEqual(
                [{
                    "key": "Content-Type",
                    "value": "application/json",
                    "description": "Indica que o corpo contém JSON.",
                    "enabled": True,
                }],
                json.loads(create.headers_json),
            )
            self.assertEqual(
                {"mode": "raw_json", "content": '{"text":"{{argument}}"}'},
                json.loads(create.body_json),
            )

            edit = definitions["notes.javascript.edit"]
            self.assertEqual("PUT", edit.method)
            self.assertTrue(edit.url.endswith("/api/notes/{{argument}}"))
            self.assertEqual(
                {
                    "mode": "raw_json",
                    "content": '{"text":"Nota {{argument}} atualizada pela IRIS"}',
                },
                json.loads(edit.body_json),
            )

            delete = definitions["notes.javascript.delete"]
            self.assertEqual("DELETE", delete.method)
            self.assertEqual([], json.loads(delete.headers_json))
            self.assertEqual(
                {"mode": "none", "content": ""},
                json.loads(delete.body_json),
            )
        finally:
            db.close()

    def test_resync_is_idempotent_and_preserves_saved_argument(self) -> None:
        self.registry.sync()
        db = self.session_factory()
        try:
            create = (
                db.query(ModuleHttpRequest)
                .join(Module)
                .filter(Module.module_public_key == "notes.javascript.create")
                .one()
            )
            create.argument = "Comprar café"
            db.commit()
        finally:
            db.close()

        self.registry.sync()

        db = self.session_factory()
        try:
            module_count = db.query(Module).filter(
                Module.module_public_key.in_(NOTES_PUBLIC_KEYS)
            ).count()
            requests = db.query(ModuleHttpRequest).join(Module).filter(
                Module.module_public_key.in_(NOTES_PUBLIC_KEYS)
            ).all()
            create = next(
                request
                for request in requests
                if request.module.module_public_key == "notes.javascript.create"
            )
            self.assertEqual(5, module_count)
            self.assertEqual(3, len(requests))
            self.assertEqual("Comprar café", create.argument)
        finally:
            db.close()

    def test_ui_shows_auto_start_only_on_root_and_execution_only_on_children(self) -> None:
        self.registry.sync()
        db = self.session_factory()
        try:
            module_ids = {
                module.module_public_key: module.id
                for module in db.query(Module).filter(
                    Module.module_public_key.in_(NOTES_PUBLIC_KEYS)
                )
            }
        finally:
            db.close()

        root_detail = get_module_detail(
            module_ids["notes.javascript"],
            self.session_factory,
        )
        root_state = ModuleViewState(root_detail, None, self.session_factory)
        self.assertNotIn("execution", [tab[0] for tab in root_state.tab_definitions])
        self.assertIsNotNone(root_state._build_auto_start_field())

        for child_key in NOTES_PUBLIC_KEYS[1:]:
            detail = get_module_detail(module_ids[child_key], self.session_factory)
            state = ModuleViewState(detail, None, self.session_factory)
            self.assertIn("execution", [tab[0] for tab in state.tab_definitions])
            self.assertIsNone(state._build_auto_start_field())


class NotesPythonAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root_adapter = load_notes_entrypoint(
            "notes_javascript",
            "notes.javascript",
        )
        cls.open_adapter = load_notes_entrypoint(
            "notes_javascript_open",
            "notes.javascript.open",
        )

    def test_root_adapter_reports_missing_node_clearly(self) -> None:
        with patch.object(self.root_adapter.shutil, "which", return_value=None):
            with self.assertRaisesRegex(
                RuntimeError,
                "Node.js não foi encontrado",
            ):
                self.root_adapter.start()

    def test_root_adapter_starts_process_without_shell(self) -> None:
        process = Mock()
        process.poll.return_value = None
        with (
            patch.object(self.root_adapter.shutil, "which", return_value="node"),
            patch.object(self.root_adapter, "_ensure_port_available"),
            patch.object(self.root_adapter, "_wait_for_health"),
            patch.object(
                self.root_adapter.subprocess,
                "Popen",
                return_value=process,
            ) as popen,
            patch("pathlib.Path.open", mock_open()),
        ):
            returned_process = self.root_adapter.start()

        arguments, = popen.call_args.args
        self.assertIs(returned_process, process)
        self.assertIsInstance(arguments, list)
        self.assertFalse(popen.call_args.kwargs["shell"])
        self.assertTrue(ModuleRuntimeManager()._is_process_handle(process))

    def test_root_adapter_rejects_occupied_port(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind(("127.0.0.1", 0))
            port = int(occupied.getsockname()[1])
            with (
                patch.dict(os.environ, {"IRIS_NOTES_PORT": str(port)}),
                patch.object(self.root_adapter.shutil, "which", return_value="node"),
            ):
                with self.assertRaisesRegex(RuntimeError, "já está em uso"):
                    self.root_adapter.start()

    def test_health_wait_detects_process_ending_during_startup(self) -> None:
        process = Mock()
        process.poll.return_value = 1

        with self.assertRaisesRegex(RuntimeError, "encerrado durante"):
            self.root_adapter._wait_for_health(process, 8765)

    def test_open_adapter_reports_offline_backend(self) -> None:
        with patch.object(
            self.open_adapter,
            "urlopen",
            side_effect=URLError("offline"),
        ):
            result = self.open_adapter.execute()

        self.assertFalse(result["success"])
        self.assertIn("Iniciar com a IRIS", result["message"])

    def test_open_adapter_opens_browser_when_backend_is_online(self) -> None:
        response = MagicMock()
        response.status = 200
        response.read.return_value = json.dumps({"success": True}).encode("utf-8")
        response.__enter__.return_value = response
        with (
            patch.object(self.open_adapter, "urlopen", return_value=response),
            patch.object(
                self.open_adapter.webbrowser,
                "open",
                return_value=True,
            ) as open_browser,
        ):
            result = self.open_adapter.execute()

        self.assertTrue(result["success"])
        open_browser.assert_called_once_with("http://127.0.0.1:8765/")

    def test_open_adapter_reports_browser_failure(self) -> None:
        response = MagicMock()
        response.status = 200
        response.read.return_value = json.dumps({"success": True}).encode("utf-8")
        response.__enter__.return_value = response
        with (
            patch.object(self.open_adapter, "urlopen", return_value=response),
            patch.object(self.open_adapter.webbrowser, "open", return_value=False),
        ):
            result = self.open_adapter.execute()

        self.assertFalse(result["success"])
        self.assertIn("navegador", result["message"])


@unittest.skipUnless(shutil.which("node"), "Node.js não está instalado.")
class NotesNodeServerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root_adapter = load_notes_entrypoint(
            "notes_javascript",
            "notes.javascript",
        )

    def setUp(self) -> None:
        self.port = self._free_port()
        self.environment_patch = patch.dict(
            os.environ,
            {"IRIS_NOTES_PORT": str(self.port)},
        )
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)
        self.process = self.root_adapter.start()
        self.addCleanup(self._stop_process)

    def _stop_process(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=5)
        self.assertIsNotNone(self.process.poll())

    def test_health_and_html_are_available(self) -> None:
        status, payload, content_type = self._request("GET", "/health")
        self.assertEqual(200, status)
        self.assertTrue(payload["success"])
        self.assertIn("application/json", content_type)

        status, html, content_type = self._request("GET", "/", parse_json=False)
        self.assertEqual(200, status)
        self.assertIn("<title>Notas</title>", html)
        self.assertIn("text/html", content_type)

    def test_note_crud_and_initial_empty_state(self) -> None:
        status, payload, _ = self._request("GET", "/api/notes")
        self.assertEqual(200, status)
        self.assertEqual([], payload["data"])

        status, created, _ = self._request(
            "POST",
            "/api/notes",
            {"text": "Comprar café"},
        )
        self.assertEqual(201, status)
        self.assertEqual({"id": 1, "text": "Comprar café"}, created["data"])

        status, updated, _ = self._request(
            "PUT",
            "/api/notes/1",
            {"text": "Comprar chá"},
        )
        self.assertEqual(200, status)
        self.assertEqual("Comprar chá", updated["data"]["text"])

        status, deleted, _ = self._request("DELETE", "/api/notes/1")
        self.assertEqual(200, status)
        self.assertEqual(1, deleted["data"]["id"])

    def test_create_validation_errors(self) -> None:
        status, payload, _ = self._request("POST", "/api/notes", {"text": ""})
        self.assertEqual(400, status)
        self.assertFalse(payload["success"])

        status, payload, _ = self._request(
            "POST",
            "/api/notes",
            raw_body=b"{invalid",
        )
        self.assertEqual(400, status)
        self.assertIn("JSON válido", payload["message"])

        status, payload, _ = self._request("POST", "/api/notes")
        self.assertEqual(400, status)
        self.assertIn("obrigatório", payload["message"])

        status, payload, _ = self._request("POST", "/api/notes", {})
        self.assertEqual(400, status)
        self.assertIn("'text'", payload["message"])

        status, payload, _ = self._request(
            "POST",
            "/api/notes",
            {"text": "a" * 501},
        )
        self.assertEqual(400, status)
        self.assertIn("500", payload["message"])

    def test_edit_validation_errors(self) -> None:
        status, payload, _ = self._request(
            "PUT",
            "/api/notes/not-an-id",
            {"text": "Texto"},
        )
        self.assertEqual(400, status)
        self.assertIn("ID", payload["message"])

        status, payload, _ = self._request(
            "PUT",
            "/api/notes/999",
            {"text": "Texto"},
        )
        self.assertEqual(404, status)
        self.assertIn("não encontrada", payload["message"])

        self._request("POST", "/api/notes", {"text": "Original"})
        status, payload, _ = self._request(
            "PUT",
            "/api/notes/1",
            raw_body=b"{invalid",
        )
        self.assertEqual(400, status)
        self.assertIn("JSON válido", payload["message"])

    def test_delete_missing_note_and_unknown_route(self) -> None:
        status, payload, _ = self._request("DELETE", "/api/notes/invalid")
        self.assertEqual(400, status)
        self.assertIn("ID", payload["message"])

        status, payload, _ = self._request("DELETE", "/api/notes/999")
        self.assertEqual(404, status)
        self.assertFalse(payload["success"])

        status, payload, _ = self._request("GET", "/missing")
        self.assertEqual(404, status)
        self.assertEqual("Rota não encontrada.", payload["message"])

    def test_wrong_method_is_rejected(self) -> None:
        status, payload, _ = self._request("PATCH", "/api/notes")
        self.assertEqual(405, status)
        self.assertEqual("Método não permitido.", payload["message"])

    def test_iris_http_children_execute_arguments_and_create_logs(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        database_path = Path(temporary_directory.name) / "notes-execution.db"
        engine = create_engine(f"sqlite:///{database_path}")
        self.addCleanup(engine.dispose)
        enable_sqlite_foreign_keys(engine)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        ModuleRegistryService(
            INSTALLED_MODULES_ROOT,
            session_factory,
        ).sync()

        db = session_factory()
        self.addCleanup(db.close)
        modules = {
            module.module_public_key: module
            for module in db.query(Module).filter(
                Module.module_public_key.in_(NOTES_PUBLIC_KEYS)
            )
        }
        for public_key in NOTES_PUBLIC_KEYS[2:]:
            request = modules[public_key].http_request
            request.url = request.url.replace(":8765", f":{self.port}")
        db.commit()

        processor = CommandProcessor(
            ModuleRepository(db),
            session_factory,
        )
        created = processor.execute_module_id(
            modules["notes.javascript.create"].id,
            "Comprar café amanhã",
        )
        self.assertEqual(201, created["status_code"])
        self.assertEqual("Comprar café amanhã", created["body"]["data"]["text"])

        edited = processor.execute_module_id(
            modules["notes.javascript.edit"].id,
            "1",
        )
        self.assertEqual(200, edited["status_code"])
        self.assertEqual("Nota 1 atualizada pela IRIS", edited["body"]["data"]["text"])

        deleted = processor.execute_module_id(
            modules["notes.javascript.delete"].id,
            "1",
        )
        self.assertEqual(200, deleted["status_code"])
        self.assertEqual(1, deleted["body"]["data"]["id"])

        success_logs = db.query(Log).filter(
            Log.module_id.in_([
                modules["notes.javascript.create"].id,
                modules["notes.javascript.edit"].id,
                modules["notes.javascript.delete"].id,
            ])
        ).all()
        self.assertEqual(3, len(success_logs))
        self.assertTrue(all(log.status == "success" for log in success_logs))
        self.assertTrue(all("HTTP " in log.message for log in success_logs))
        self.assertTrue(all("Comprar café" not in log.message for log in success_logs))

        self.process.terminate()
        self.process.wait(timeout=5)
        offline = processor.execute_module_id(
            modules["notes.javascript.create"].id,
            "Sem servidor",
        )
        self.assertFalse(offline["success"])
        error_log = db.query(Log).filter(
            Log.module_id == modules["notes.javascript.create"].id,
            Log.status == "error",
        ).one()
        self.assertIn("falha antes da resposta", error_log.message)
        self.assertNotIn("Sem servidor", error_log.message)

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, object] | None = None,
        *,
        raw_body: bytes | None = None,
        parse_json: bool = True,
    ) -> tuple[int, object, str]:
        data = raw_body
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if data is not None else {},
        )
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as error:
            response = error
        with response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            content = response.read().decode("utf-8")
        payload = json.loads(content) if parse_json else content
        return status, payload, content_type

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            return int(probe.getsockname()[1])


class NotesHtmlTests(unittest.TestCase):
    def test_html_uses_api_without_inner_html_injection(self) -> None:
        html = (
            INSTALLED_MODULES_ROOT
            / "notes_javascript"
            / "public"
            / "index.html"
        ).read_text(encoding="utf-8")

        self.assertIn("/api/notes", html)
        self.assertIn("text.textContent = note.text", html)
        self.assertNotIn("innerHTML", html)


if __name__ == "__main__":
    unittest.main()
