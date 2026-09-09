import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base, enable_sqlite_foreign_keys
from database.models import Routine
from services.routine_scheduler_service import RoutineSchedulerService


class FakeScheduler:
    def __init__(self) -> None:
        self.jobs = {}
        self.start_calls = 0
        self.shutdown_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def shutdown(self, wait=False) -> None:
        self.shutdown_calls += 1

    def add_job(self, function, **kwargs) -> None:
        values = dict(kwargs)
        job_id = values.pop("id")
        self.jobs[job_id] = SimpleNamespace(
            id=job_id,
            function=function,
            **values,
        )

    def remove_job(self, job_id: str) -> None:
        self.jobs.pop(job_id, None)

    def get_jobs(self):
        return list(self.jobs.values())

    def get_job(self, job_id: str):
        return self.jobs.get(job_id)


class RoutineSchedulerServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        database_path = Path(temporary_directory.name) / "scheduler.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        self.addCleanup(self.engine.dispose)
        enable_sqlite_foreign_keys(self.engine)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.scheduler = FakeScheduler()
        self.service = RoutineSchedulerService(
            self.session_factory,
            scheduler=self.scheduler,
        )

    def test_start_loads_only_valid_active_non_deleted_routines(self) -> None:
        valid_id = self._create_routine("0 8 * * mon", active=True)
        self._create_routine("0 8 * * tue", active=False)
        self._create_routine("cron inválido", active=True)
        self._create_routine("0 9 1 * *", active=True, deleted=True)

        self.service.start()

        self.assertEqual({f"routine-{valid_id}"}, set(self.scheduler.jobs))
        job = self.scheduler.jobs[f"routine-{valid_id}"]
        self.assertEqual(1, job.max_instances)
        self.assertTrue(job.coalesce)
        self.assertEqual(1, job.misfire_grace_time)

    def test_start_is_idempotent_and_does_not_duplicate_jobs(self) -> None:
        routine_id = self._create_routine("0 8 * * mon", active=True)
        self.service.start()
        first_job = self.scheduler.get_job(f"routine-{routine_id}")

        self.service.start()

        self.assertEqual(1, self.scheduler.start_calls)
        self.assertIs(first_job, self.scheduler.get_job(f"routine-{routine_id}"))

    def test_sync_replaces_job_and_removes_it_when_deactivated_or_deleted(self) -> None:
        routine_id = self._create_routine("0 8 * * mon", active=True)
        self.service.start()
        db = self.session_factory()
        try:
            routine = db.query(Routine).filter(Routine.id == routine_id).one()
            routine.cron_expression = "30 18 * * fri"
            db.commit()
        finally:
            db.close()

        self.assertTrue(self.service.sync_routine(routine_id))
        self.assertIsNotNone(self.scheduler.get_job(f"routine-{routine_id}"))
        self.assertEqual(
            "cron[month='*', day='*', day_of_week='fri', hour='18', minute='30']",
            str(self.scheduler.get_job(f"routine-{routine_id}").trigger),
        )

        db = self.session_factory()
        try:
            routine = db.query(Routine).filter(Routine.id == routine_id).one()
            routine.active = False
            db.commit()
        finally:
            db.close()
        self.service.sync_routine(routine_id)
        self.assertIsNone(self.scheduler.get_job(f"routine-{routine_id}"))

        db = self.session_factory()
        try:
            routine = db.query(Routine).filter(Routine.id == routine_id).one()
            routine.active = True
            routine.deleted_at = routine.created_at
            db.commit()
        finally:
            db.close()
        self.service.sync_routine(routine_id)
        self.assertIsNone(self.scheduler.get_job(f"routine-{routine_id}"))

    def test_invalid_routine_does_not_prevent_other_jobs_from_loading(self) -> None:
        self._create_routine("inválido", active=True)
        valid_id = self._create_routine("0 10 * * sat,sun", active=True)

        self.service.start()

        self.assertTrue(self.service.has_job(valid_id))
        self.assertEqual(1, len(self.scheduler.jobs))

    def test_shutdown_is_safe_and_idempotent(self) -> None:
        self.service.start()
        self.service.shutdown()
        self.service.shutdown()
        self.assertEqual(1, self.scheduler.shutdown_calls)

    def _create_routine(
        self,
        cron_expression: str,
        *,
        active: bool,
        deleted: bool = False,
    ) -> int:
        db = self.session_factory()
        try:
            routine = Routine(
                name="Teste",
                cron_expression=cron_expression,
                active=active,
                stop_on_failure=True,
            )
            db.add(routine)
            db.flush()
            if deleted:
                routine.deleted_at = routine.created_at
            db.commit()
            return routine.id
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
