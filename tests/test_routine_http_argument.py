import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.command_processor import CommandProcessor
from database.db import Base, enable_sqlite_foreign_keys
from database.models import Log, Module, ModuleHttpRequest, Routine
from repositories.module_repository import ModuleRepository
from services.http_service import ModuleHttpRequestService


class FakeHttpService:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def request(self, method, url, **kwargs):
        self.urls.append(url)
        return {
            "success": True,
            "message": "Concluído.",
            "status_code": 200,
            "elapsed_ms": 1,
        }


class RoutineHttpArgumentTests(unittest.TestCase):
    def test_routine_argument_does_not_replace_global_http_argument(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        database_path = Path(temporary_directory.name) / "http-routine.db"
        engine = create_engine(f"sqlite:///{database_path}")
        self.addCleanup(engine.dispose)
        enable_sqlite_foreign_keys(engine)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        db = session_factory()
        try:
            module = Module(
                module_public_key="test.routine-http",
                name="HTTP",
                call_name="http",
                is_executable=True,
                is_available=True,
            )
            routine = Routine(
                name="Teste",
                cron_expression="0 8 * * mon",
                active=True,
                stop_on_failure=True,
            )
            db.add_all([module, routine])
            db.flush()
            db.add(
                ModuleHttpRequest(
                    module_id=module.id,
                    method="GET",
                    url="https://example.com/{{argument}}",
                    argument_enabled=True,
                    argument="valor-global",
                )
            )
            db.commit()
            module_id = module.id
            routine_id = routine.id

            http_service = FakeHttpService()
            processor = CommandProcessor(ModuleRepository(db), session_factory)
            processor.http_request_service = ModuleHttpRequestService(
                session_factory,
                http_service=http_service,
            )
            processor.execute_module_id(
                module_id,
                "valor-da-rotina",
                routine_id=routine_id,
            )

            db.expire_all()
            request = db.query(ModuleHttpRequest).one()
            log = db.query(Log).one()
            self.assertEqual("valor-global", request.argument)
            self.assertEqual(["https://example.com/valor-da-rotina"], http_service.urls)
            self.assertEqual(routine_id, log.routine_id)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
