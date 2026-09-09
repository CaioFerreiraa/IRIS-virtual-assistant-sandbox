from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, joinedload, selectinload

from database.models import Routine, RoutineAction


class RoutineRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_routines(self, *, include_deleted: bool = False) -> list[Routine]:
        query = self.db.query(Routine).options(
            selectinload(Routine.routine_actions).joinedload(RoutineAction.module)
        )
        if not include_deleted:
            query = query.filter(Routine.deleted_at.is_(None))
        return query.order_by(Routine.created_at.desc(), Routine.id.desc()).all()

    def list_active_routines(self) -> list[Routine]:
        return (
            self.db.query(Routine)
            .filter(
                Routine.active.is_(True),
                Routine.deleted_at.is_(None),
            )
            .order_by(Routine.id)
            .all()
        )

    def get_by_id(
        self,
        routine_id: int,
        *,
        include_deleted: bool = False,
    ) -> Routine | None:
        query = (
            self.db.query(Routine)
            .options(
                selectinload(Routine.routine_actions).joinedload(
                    RoutineAction.module
                )
            )
            .filter(Routine.id == routine_id)
        )
        if not include_deleted:
            query = query.filter(Routine.deleted_at.is_(None))
        return query.one_or_none()

    def list_routine_actions(
        self,
        routine_id: int | None = None,
        *,
        active_only: bool = False,
    ) -> list[RoutineAction]:
        query = self.db.query(RoutineAction).options(joinedload(RoutineAction.module))
        if routine_id is not None:
            query = query.filter(RoutineAction.routine_id == routine_id)
        if active_only:
            query = query.filter(RoutineAction.active.is_(True))
        return query.order_by(
            RoutineAction.execution_order,
            RoutineAction.id,
        ).all()

    def create_routine(
        self,
        name: str,
        cron_expression: str,
        *,
        active: bool,
        stop_on_failure: bool,
    ) -> Routine:
        routine = Routine(
            name=name,
            cron_expression=cron_expression,
            active=active,
            stop_on_failure=stop_on_failure,
        )
        self.db.add(routine)
        self.db.flush()
        return routine

    def create_routine_action(
        self,
        routine_id: int,
        module_id: int,
        execution_order: int = 1,
        *,
        active: bool = True,
        argument: str | None = None,
    ) -> RoutineAction:
        routine_action = RoutineAction(
            routine_id=routine_id,
            module_id=module_id,
            execution_order=execution_order,
            active=active,
            argument=argument,
        )
        self.db.add(routine_action)
        self.db.flush()
        return routine_action

    def delete_action(self, routine_action: RoutineAction) -> None:
        self.db.delete(routine_action)

    def set_active(self, routine: Routine, active: bool) -> None:
        routine.active = active

    def soft_delete(self, routine: Routine, deleted_at: datetime) -> None:
        routine.active = False
        routine.deleted_at = deleted_at

    def update_last_run(self, routine: Routine, run_at: datetime) -> None:
        routine.last_run_at = run_at
