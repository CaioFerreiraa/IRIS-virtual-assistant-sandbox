import tempfile
import threading
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.routine_executor import RoutineExecutor
from database.db import Base, enable_sqlite_foreign_keys
from database.models import Log, Module, Routine, RoutineAction


class FakeProcessor:
    def __init__(self, outcomes, calls, *, entered=None, release=None) -> None:
        self.outcomes = outcomes
        self.calls = calls
        self.entered = entered
        self.release = release

    def execute_module_id(self, module_id, argument=None, routine_id=None):
        self.calls.append((module_id, argument, routine_id))
        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            self.release.wait(timeout=3)
        outcome = self.outcomes[module_id]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RoutineExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root = Path(self.temporary_directory.name)
        self.engine = create_engine(f"sqlite:///{root / 'executor.db'}")
        self.addCleanup(self.engine.dispose)
        enable_sqlite_foreign_keys(self.engine)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.module_ids = self._create_modules(3)

    def test_executes_modules_in_order_and_returns_success(self) -> None:
        routine_id = self._create_routine(
            [self.module_ids[1], self.module_ids[0], self.module_ids[2]],
        )
        calls = []
        outcomes = {
            module_id: {"success": True, "message": "OK"}
            for module_id in self.module_ids
        }
        executor = RoutineExecutor(
            self.session_factory,
            processor_factory=lambda db: FakeProcessor(outcomes, calls),
        )

        result = executor.execute(routine_id)

        self.assertEqual("success", result["status"])
        self.assertEqual(3, result["executed"])
        self.assertEqual(
            [self.module_ids[1], self.module_ids[0], self.module_ids[2]],
            [call[0] for call in calls],
        )
        self.assertTrue(all(call[2] == routine_id for call in calls))
        self.assertIsNotNone(self._load_routine(routine_id).last_run_at)

    def test_stops_after_success_false_when_configured(self) -> None:
        routine_id = self._create_routine(self.module_ids, stop_on_failure=True)
        calls = []
        outcomes = {
            self.module_ids[0]: {"success": False, "message": "Falhou"},
            self.module_ids[1]: {"success": True},
            self.module_ids[2]: {"success": True},
        }
        executor = RoutineExecutor(
            self.session_factory,
            processor_factory=lambda db: FakeProcessor(outcomes, calls),
        )

        result = executor.execute(routine_id)

        self.assertEqual("error", result["status"])
        self.assertTrue(result["interrupted"])
        self.assertEqual(1, result["executed"])
        self.assertEqual(2, result["skipped"])
        self.assertEqual(["error", "skipped", "skipped"], [s["status"] for s in result["steps"]])

    def test_continues_after_exception_and_returns_partial(self) -> None:
        routine_id = self._create_routine(self.module_ids, stop_on_failure=False)
        calls = []
        outcomes = {
            self.module_ids[0]: RuntimeError("Falha prevista"),
            self.module_ids[1]: {"success": True, "message": "OK"},
            self.module_ids[2]: {"success": False, "message": "Retorno falso"},
        }
        executor = RoutineExecutor(
            self.session_factory,
            processor_factory=lambda db: FakeProcessor(outcomes, calls),
        )

        result = executor.execute(routine_id)

        self.assertEqual("partial", result["status"])
        self.assertEqual(3, result["executed"])
        self.assertEqual(2, result["failures"])
        self.assertFalse(result["interrupted"])

    def test_unavailable_module_is_a_controlled_failure(self) -> None:
        routine_id = self._create_routine([self.module_ids[0]])
        db = self.session_factory()
        try:
            module = db.query(Module).filter(Module.id == self.module_ids[0]).one()
            module.is_available = False
            db.commit()
        finally:
            db.close()
        calls = []
        executor = RoutineExecutor(
            self.session_factory,
            processor_factory=lambda db: FakeProcessor(
                {self.module_ids[0]: ValueError("Módulo indisponível")},
                calls,
            ),
        )

        result = executor.execute(routine_id)

        self.assertEqual("error", result["status"])
        self.assertIn("indisponível", result["steps"][0]["message"])
        self.assertIsNotNone(self._load_routine(routine_id).last_run_at)

    def test_real_command_processor_records_routine_id_in_log(self) -> None:
        entrypoint = Path(self.temporary_directory.name) / "success.py"
        entrypoint.write_text(
            "def execute(argument=None):\n"
            "    return {'success': True, 'message': 'Concluído.'}\n",
            encoding="utf-8",
        )
        db = self.session_factory()
        try:
            module = db.query(Module).filter(Module.id == self.module_ids[0]).one()
            module.request_method = "PYTHON"
            module.request_url = str(entrypoint)
            db.commit()
        finally:
            db.close()
        routine_id = self._create_routine([self.module_ids[0]], arguments=["fixo"])

        result = RoutineExecutor(self.session_factory).execute(routine_id)

        self.assertEqual("success", result["status"])
        db = self.session_factory()
        try:
            log = db.query(Log).one()
            self.assertEqual(routine_id, log.routine_id)
            self.assertEqual(self.module_ids[0], log.module_id)
        finally:
            db.close()

    def test_same_routine_cannot_run_twice_at_the_same_time(self) -> None:
        routine_id = self._create_routine([self.module_ids[0]])
        calls = []
        entered = threading.Event()
        release = threading.Event()
        outcomes = {self.module_ids[0]: {"success": True}}
        executor = RoutineExecutor(
            self.session_factory,
            processor_factory=lambda db: FakeProcessor(
                outcomes,
                calls,
                entered=entered,
                release=release,
            ),
        )
        first_result = []
        thread = threading.Thread(
            target=lambda: first_result.append(executor.execute(routine_id))
        )
        thread.start()
        self.assertTrue(entered.wait(timeout=2))

        second_result = executor.execute(routine_id)
        release.set()
        thread.join(timeout=3)

        self.assertTrue(second_result["already_running"])
        self.assertEqual("error", second_result["status"])
        self.assertEqual("success", first_result[0]["status"])

    def _create_modules(self, count: int) -> list[int]:
        db = self.session_factory()
        try:
            modules = [
                Module(
                    module_public_key=f"test.module-{index}",
                    name=f"Módulo {index}",
                    call_name=f"modulo-{index}",
                    is_executable=True,
                    is_available=True,
                    request_method="GET",
                    request_url=f"https://example.com/{index}",
                )
                for index in range(count)
            ]
            db.add_all(modules)
            db.commit()
            return [module.id for module in modules]
        finally:
            db.close()

    def _create_routine(
        self,
        module_ids,
        *,
        stop_on_failure=True,
        arguments=None,
    ) -> int:
        db = self.session_factory()
        try:
            routine = Routine(
                name="Teste",
                cron_expression="0 8 * * mon",
                active=True,
                stop_on_failure=stop_on_failure,
            )
            db.add(routine)
            db.flush()
            for order, module_id in enumerate(module_ids, start=1):
                db.add(
                    RoutineAction(
                        routine_id=routine.id,
                        module_id=module_id,
                        execution_order=order,
                        active=True,
                        argument=(arguments or [None] * len(module_ids))[order - 1],
                    )
                )
            db.commit()
            return routine.id
        finally:
            db.close()

    def _load_routine(self, routine_id: int) -> Routine:
        db = self.session_factory()
        try:
            routine = db.query(Routine).filter(Routine.id == routine_id).one()
            db.expunge(routine)
            return routine
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
