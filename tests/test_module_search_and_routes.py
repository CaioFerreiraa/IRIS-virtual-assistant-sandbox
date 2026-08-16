import tempfile
import unittest
from pathlib import Path

import flet as ft
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.routes import build_route_content
from database.db import Base, enable_sqlite_foreign_keys
from database.models import Module
from repositories.module_repository import ModuleRepository
from ui.home.dropdowns import (
    filter_modules,
    resolve_typed_module,
    resolve_voice_module_option,
)


class ModuleSearchAndRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        database_path = Path(self.temporary_directory.name) / "routes.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        self.addCleanup(self.engine.dispose)
        enable_sqlite_foreign_keys(self.engine)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        db = self.session_factory()
        try:
            module = Module(
                module_public_key="weather",
                name="Clima",
                call_name="clima",
                custom_call_name="tempo",
                is_executable=True,
                is_available=True,
                request_method="PYTHON",
                request_url="module.py",
            )
            db.add(module)
            db.commit()
            self.module_id = module.id
        finally:
            db.close()

    def options(self) -> list[dict[str, object]]:
        db = self.session_factory()
        try:
            return ModuleRepository(db).list_module_options()
        finally:
            db.close()

    def test_searches_by_original_call_name(self) -> None:
        matches = filter_modules("clima", self.options())
        self.assertEqual(self.module_id, matches[0]["module_id"])

    def test_searches_by_custom_call_name(self) -> None:
        matches = filter_modules("tempo", self.options())
        self.assertEqual(self.module_id, matches[0]["module_id"])
        resolved = resolve_typed_module("tempo", self.options())
        self.assertEqual(self.module_id, resolved.module_id)

    def test_voice_resolution_returns_module_id(self) -> None:
        resolved = resolve_voice_module_option("tempo amanhã", self.options())
        self.assertEqual(self.module_id, resolved.module_id)
        self.assertEqual("amanhã", resolved.argument)

    def test_ambiguous_custom_call_name_is_not_resolved_silently(self) -> None:
        db = self.session_factory()
        try:
            db.add(
                Module(
                    module_public_key="weather.second",
                    name="Outro clima",
                    call_name="meteorologia",
                    custom_call_name="tempo",
                    is_executable=True,
                    is_available=True,
                    request_method="PYTHON",
                    request_url="other.py",
                )
            )
            db.commit()
        finally:
            db.close()

        resolved = resolve_typed_module("tempo", self.options())
        self.assertTrue(resolved.ambiguous)

    def test_route_with_existing_module_builds_module_screen(self) -> None:
        control = build_route_content(
            f"/modules/{self.module_id}",
            module_session_factory=self.session_factory,
        )
        texts = _collect_text_values(control)
        self.assertIn("Clima", texts)
        self.assertNotIn("Módulo não encontrado", texts)

    def test_route_with_missing_or_invalid_id_is_friendly(self) -> None:
        missing_control = build_route_content(
            "/modules/99999",
            module_session_factory=self.session_factory,
        )
        invalid_control = build_route_content(
            "/modules/not-a-number",
            module_session_factory=self.session_factory,
        )
        self.assertIn("Módulo não encontrado", _collect_text_values(missing_control))
        self.assertIn("Módulo não encontrado", _collect_text_values(invalid_control))


def _collect_text_values(control: ft.Control) -> list[str]:
    values: list[str] = []
    if isinstance(control, ft.Text):
        values.append(str(control.value))
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        values.extend(_collect_text_values(content))
    for child in getattr(control, "controls", ()) or ():
        if isinstance(child, ft.Control):
            values.extend(_collect_text_values(child))
    return values


if __name__ == "__main__":
    unittest.main()
