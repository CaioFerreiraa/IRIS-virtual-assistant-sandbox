import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.command_processor import CommandProcessor
from database.db import Base, enable_sqlite_foreign_keys
from database.models import Log, Module, ModuleVariableDefinition
from repositories.module_repository import ModuleRepository


class ModuleExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root = Path(self.temporary_directory.name)
        self.engine = create_engine(f"sqlite:///{root / 'execution.db'}")
        self.addCleanup(self.engine.dispose)
        enable_sqlite_foreign_keys(self.engine)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.entrypoint = root / "main.py"
        self.entrypoint.write_text(
            """\
def execute(argument=None, variables=None):
    return {
        "success": True,
        "message": f"{variables['prefix']}:{argument}",
    }
""",
            encoding="utf-8",
        )

    def test_execution_uses_module_id_and_validated_variables(self) -> None:
        db = self.session_factory()
        try:
            module = Module(
                module_public_key="example.execution",
                name="Exemplo",
                call_name="exemplo",
                is_executable=True,
                is_available=True,
                request_method="PYTHON",
                request_url=str(self.entrypoint),
            )
            db.add(module)
            db.flush()
            db.add(
                ModuleVariableDefinition(
                    module_id=module.id,
                    key="prefix",
                    label="Prefixo",
                    description="Prefixo técnico.",
                    type="text",
                    is_required=True,
                    is_user_editable=False,
                    default_value="IRIS",
                    display_order=0,
                )
            )
            db.commit()

            result = CommandProcessor(ModuleRepository(db)).execute_module_id(
                module.id,
                "ok",
            )
            self.assertEqual("IRIS:ok", result["message"])
            self.assertEqual(1, db.query(Log).filter(Log.module_id == module.id).count())
        finally:
            db.close()

    def test_required_variable_is_validated_before_execution(self) -> None:
        db = self.session_factory()
        try:
            module = Module(
                module_public_key="example.required",
                name="Obrigatório",
                call_name="obrigatorio",
                is_executable=True,
                is_available=True,
                request_method="PYTHON",
                request_url=str(self.entrypoint),
            )
            db.add(module)
            db.flush()
            db.add(
                ModuleVariableDefinition(
                    module_id=module.id,
                    key="prefix",
                    label="Prefixo",
                    type="text",
                    is_required=True,
                    is_user_editable=True,
                    default_value="",
                    display_order=0,
                )
            )
            db.commit()

            with self.assertRaisesRegex(ValueError, "Prefixo"):
                CommandProcessor(ModuleRepository(db)).execute_module_id(module.id)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
