import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base, enable_sqlite_foreign_keys
from database.models import Module
from services.module_registry_state import get_module_registry_state
from services.module_runtime_service import ModuleRuntimeManager


class ModuleRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.engine = create_engine(f"sqlite:///{self.root / 'runtime.db'}")
        self.addCleanup(self.engine.dispose)
        enable_sqlite_foreign_keys(self.engine)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.manager = ModuleRuntimeManager(self.session_factory)

    def create_backend(self, public_key: str, source: str) -> tuple[int, Path]:
        folder = self.root / public_key
        folder.mkdir()
        entrypoint = folder / "main.py"
        entrypoint.write_text(source, encoding="utf-8")
        db = self.session_factory()
        try:
            module = Module(
                module_public_key=public_key,
                name=public_key,
                call_name=public_key,
                is_available=True,
                is_executable=False,
                request_method="PYTHON",
                request_url=str(entrypoint),
                manifest_directory=str(folder),
                runtime_type="python",
                supports_auto_start=True,
                auto_start_enabled=True,
            )
            db.add(module)
            db.commit()
            return module.id, folder
        finally:
            db.close()

    def test_backend_start_updates_runtime_status(self) -> None:
        module_id, _ = self.create_backend(
            "backend",
            "def start():\n    return None\n",
        )
        self.manager._start_backend(module_id)
        self.assertEqual(
            "online",
            get_module_registry_state().runtime_statuses[module_id],
        )

    def test_backend_failure_does_not_prevent_another_start(self) -> None:
        broken_id, broken_folder = self.create_backend(
            "broken",
            "def start():\n    raise RuntimeError('startup failed')\n",
        )
        valid_id, _ = self.create_backend(
            "valid",
            "def start():\n    return None\n",
        )

        self.manager._start_backend(broken_id)
        self.manager._start_backend(valid_id)

        statuses = get_module_registry_state().runtime_statuses
        self.assertEqual("com erro", statuses[broken_id])
        self.assertEqual("online", statuses[valid_id])
        self.assertTrue((broken_folder / "module.log").is_file())
        db = self.session_factory()
        try:
            broken_module = db.query(Module).filter(Module.id == broken_id).one()
            valid_module = db.query(Module).filter(Module.id == valid_id).one()
            self.assertFalse(broken_module.is_available)
            self.assertTrue(valid_module.is_available)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
