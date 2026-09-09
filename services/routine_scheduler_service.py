from __future__ import annotations

import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import SchedulerNotRunningError
from apscheduler.jobstores.base import JobLookupError

from core.routine_executor import RoutineExecutor
from database.db import SessionLocal
from repositories.routine_repository import RoutineRepository
from services.routine_schedule_service import RoutineScheduleService


LOGGER = logging.getLogger("iris.routines")
JOB_ID_PREFIX = "routine-"


class RoutineSchedulerService:
    def __init__(
        self,
        session_factory=SessionLocal,
        *,
        schedule_service: RoutineScheduleService | None = None,
        scheduler=None,
        executor: RoutineExecutor | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.schedule_service = schedule_service or RoutineScheduleService()
        self.executor = executor or RoutineExecutor(session_factory)
        self._scheduler = scheduler
        self._provided_scheduler = scheduler
        self._started = False
        self._state_lock = threading.Lock()

    @property
    def started(self) -> bool:
        return self._started

    def start(self) -> None:
        with self._state_lock:
            if self._started:
                return
            if self._scheduler is None:
                self._scheduler = BackgroundScheduler(
                    timezone=self.schedule_service.local_timezone,
                )
            self._scheduler.start()
            self._started = True
        self.reload_active_routines()

    def shutdown(self) -> None:
        with self._state_lock:
            if not self._started or self._scheduler is None:
                return
            scheduler = self._scheduler
            self._started = False
        try:
            scheduler.shutdown(wait=False)
        except SchedulerNotRunningError:
            pass
        except Exception:
            LOGGER.exception("Falha ao encerrar o scheduler de rotinas.")
        finally:
            if self._provided_scheduler is None:
                self._scheduler = None

    def reload_active_routines(self) -> None:
        if not self._started or self._scheduler is None:
            return
        db = self.session_factory()
        try:
            routines = RoutineRepository(db).list_active_routines()
            active_ids = {routine.id for routine in routines}
        except Exception:
            LOGGER.exception("Falha ao carregar rotinas ativas no scheduler.")
            return
        finally:
            db.close()

        for job in tuple(self._scheduler.get_jobs()):
            if not str(job.id).startswith(JOB_ID_PREFIX):
                continue
            raw_routine_id = str(job.id)[len(JOB_ID_PREFIX) :]
            if not raw_routine_id.isdigit() or int(raw_routine_id) not in active_ids:
                self._remove_job(str(job.id))

        for routine in routines:
            try:
                self._schedule(routine.id, routine.cron_expression)
            except ValueError as error:
                self._remove_job(self.job_id(routine.id))
                LOGGER.warning(
                    "Rotina %s ignorada por possuir agendamento inválido: %s",
                    routine.id,
                    error,
                )
            except Exception:
                self._remove_job(self.job_id(routine.id))
                LOGGER.exception(
                    "Falha ao carregar a rotina %s no scheduler.",
                    routine.id,
                )

    def sync_routine(self, routine_id: int) -> bool:
        if not self._started or self._scheduler is None:
            return True
        db = self.session_factory()
        try:
            routine = RoutineRepository(db).get_by_id(routine_id)
            if routine is None or not bool(routine.active):
                self._remove_job(self.job_id(routine_id))
                return True
            self._schedule(routine.id, routine.cron_expression)
            return True
        except Exception:
            self._remove_job(self.job_id(routine_id))
            LOGGER.exception(
                "Falha ao sincronizar a rotina %s com o scheduler.",
                routine_id,
            )
            return False
        finally:
            db.close()

    def remove_routine(self, routine_id: int) -> bool:
        if not self._started or self._scheduler is None:
            return True
        return self._remove_job(self.job_id(routine_id))

    def has_job(self, routine_id: int) -> bool:
        if not self._started or self._scheduler is None:
            return False
        return self._scheduler.get_job(self.job_id(routine_id)) is not None

    def job_id(self, routine_id: int) -> str:
        return f"{JOB_ID_PREFIX}{routine_id}"

    def _schedule(self, routine_id: int, cron_expression: str | None) -> None:
        if self._scheduler is None:
            return
        trigger = self.schedule_service.build_trigger(cron_expression)
        self._scheduler.add_job(
            self._run_job,
            trigger=trigger,
            id=self.job_id(routine_id),
            args=[routine_id],
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=1,
        )

    def _run_job(self, routine_id: int) -> None:
        try:
            result = self.executor.execute(routine_id)
            if result.get("status") == "error":
                LOGGER.warning(
                    "A execução agendada da rotina %s terminou com falha.",
                    routine_id,
                )
        except Exception:
            LOGGER.exception(
                "Falha técnica ao executar a rotina agendada %s.",
                routine_id,
            )

    def _remove_job(self, job_id: str) -> bool:
        if self._scheduler is None:
            return True
        try:
            self._scheduler.remove_job(job_id)
            return True
        except JobLookupError:
            return True
        except Exception:
            LOGGER.exception("Falha ao remover o job %s do scheduler.", job_id)
            return False


routine_scheduler_service = RoutineSchedulerService()
