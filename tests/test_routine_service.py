import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base, enable_sqlite_foreign_keys
from database.models import Log, Module, ModuleHttpRequest, Routine, RoutineAction
from services.routine_service import RoutineService


class FakeScheduler:
    def __init__(self) -> None:
        self.synced: list[int] = []
        self.removed: list[int] = []

    def sync_routine(self, routine_id: int) -> bool:
        self.synced.append(routine_id)
        return True

    def remove_routine(self, routine_id: int) -> bool:
        self.removed.append(routine_id)
        return True


class RoutineServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        database_path = Path(self.temporary_directory.name) / "routines.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        self.addCleanup(self.engine.dispose)
        enable_sqlite_foreign_keys(self.engine)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.scheduler = FakeScheduler()
        self.service = RoutineService(
            self.session_factory,
            scheduler_service=self.scheduler,
        )
        self.first_module_id, self.second_module_id = self._create_modules()

    def test_create_persists_routine_and_normalized_actions_in_one_transaction(self) -> None:
        created = self._create_routine(
            actions=[
                {"module_id": self.second_module_id},
                {"module_id": self.first_module_id},
            ]
        )

        db = self.session_factory()
        try:
            routine = db.query(Routine).filter(Routine.id == created["id"]).one()
            actions = (
                db.query(RoutineAction)
                .filter(RoutineAction.routine_id == routine.id)
                .order_by(RoutineAction.execution_order)
                .all()
            )
            self.assertEqual("30 18 * * mon,wed,fri", routine.cron_expression)
            self.assertTrue(routine.stop_on_failure)
            self.assertEqual([1, 2], [action.execution_order for action in actions])
            self.assertEqual(
                [self.second_module_id, self.first_module_id],
                [action.module_id for action in actions],
            )
            self.assertEqual([routine.id], self.scheduler.synced)
        finally:
            db.close()

    def test_list_ignores_soft_deleted_routines(self) -> None:
        created = self._create_routine()
        self.service.delete_routine(int(created["id"]))

        self.assertEqual([], self.service.list_routines())
        db = self.session_factory()
        try:
            routine = db.query(Routine).filter(Routine.id == created["id"]).one()
            self.assertIsNotNone(routine.deleted_at)
            self.assertFalse(routine.active)
            self.assertEqual([routine.id], self.scheduler.removed)
        finally:
            db.close()

    def test_update_reorders_and_replaces_actions(self) -> None:
        created = self._create_routine(
            actions=[
                {"module_id": self.first_module_id},
                {"module_id": self.second_module_id},
            ]
        )
        first, second = created["actions"]

        updated = self.service.update_routine(
            int(created["id"]),
            name="Rotina editada",
            schedule_type="monthly",
            days=[1, 15],
            time_value="09:00",
            active=False,
            stop_on_failure=False,
            actions=[
                {
                    "action_id": second["action_id"],
                    "module_id": second["module_id"],
                },
                {
                    "action_id": first["action_id"],
                    "module_id": first["module_id"],
                },
                {"module_id": self.first_module_id},
            ],
        )

        self.assertEqual("Rotina editada", updated["name"])
        self.assertEqual("0 9 1,15 * *", updated["cron_expression"])
        self.assertFalse(updated["stop_on_failure"])
        self.assertEqual(
            [self.second_module_id, self.first_module_id, self.first_module_id],
            [action["module_id"] for action in updated["actions"]],
        )
        self.assertEqual(
            [1, 2, 3],
            [action["execution_order"] for action in updated["actions"]],
        )

    def test_set_active_validates_saved_cron_and_synchronizes_scheduler(self) -> None:
        created = self._create_routine(active=False)
        activated = self.service.set_active(int(created["id"]), True)
        self.assertTrue(activated["active"])

        db = self.session_factory()
        try:
            routine = db.query(Routine).filter(Routine.id == created["id"]).one()
            routine.cron_expression = "inválido"
            routine.active = False
            db.commit()
        finally:
            db.close()
        with self.assertRaisesRegex(ValueError, "corrigido"):
            self.service.set_active(int(created["id"]), True)

    def test_invalid_action_rolls_back_the_whole_create(self) -> None:
        with self.assertRaisesRegex(ValueError, "não existe"):
            self._create_routine(
                actions=[
                    {"module_id": self.first_module_id},
                    {"module_id": 999999},
                ]
            )
        db = self.session_factory()
        try:
            self.assertEqual(0, db.query(Routine).count())
            self.assertEqual(0, db.query(RoutineAction).count())
        finally:
            db.close()

    def test_http_argument_is_required_and_does_not_accept_credentials(self) -> None:
        db = self.session_factory()
        try:
            module = Module(
                module_public_key="test.http",
                name="HTTP",
                call_name="http",
                is_executable=True,
                is_available=True,
            )
            db.add(module)
            db.flush()
            db.add(
                ModuleHttpRequest(
                    module_id=module.id,
                    method="POST",
                    url="https://example.com/{{argument}}",
                    argument_enabled=True,
                )
            )
            db.commit()
            module_id = module.id
        finally:
            db.close()

        with self.assertRaisesRegex(ValueError, "obrigatório"):
            self._create_routine(actions=[{"module_id": module_id}])
        with self.assertRaisesRegex(ValueError, "credencial"):
            self._create_routine(
                actions=[{"module_id": module_id, "argument": "token=segredo"}]
            )

    def test_soft_delete_preserves_historical_log_relationship(self) -> None:
        created = self._create_routine()
        db = self.session_factory()
        try:
            log = Log(
                module_id=self.first_module_id,
                routine_id=int(created["id"]),
                status="success",
                message="Concluído.",
            )
            db.add(log)
            db.commit()
            log_id = log.id
        finally:
            db.close()

        self.service.delete_routine(int(created["id"]))
        db = self.session_factory()
        try:
            log = db.query(Log).filter(Log.id == log_id).one()
            self.assertEqual(created["id"], log.routine_id)
            self.assertEqual("Rotina de teste", log.routine.name)
        finally:
            db.close()

    def _create_modules(self) -> tuple[int, int]:
        db = self.session_factory()
        try:
            first = Module(
                module_public_key="test.first",
                name="Primeiro",
                call_name="primeiro",
                is_executable=True,
                is_available=True,
                request_method="GET",
                request_url="https://example.com/first",
            )
            second = Module(
                module_public_key="test.second",
                name="Segundo",
                call_name="segundo",
                is_executable=True,
                is_available=True,
                request_method="GET",
                request_url="https://example.com/second",
            )
            db.add_all([first, second])
            db.commit()
            return first.id, second.id
        finally:
            db.close()

    def _create_routine(
        self,
        *,
        actions=None,
        active: bool = True,
    ) -> dict[str, object]:
        return self.service.create_routine(
            name="  Rotina de teste  ",
            schedule_type="weekly",
            days=["fri", "mon", "wed"],
            time_value="18:30",
            active=active,
            stop_on_failure=True,
            actions=actions or [{"module_id": self.first_module_id}],
        )


if __name__ == "__main__":
    unittest.main()
