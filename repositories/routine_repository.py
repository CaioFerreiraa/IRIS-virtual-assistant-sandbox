from sqlalchemy.orm import Session

from database.models import Routine, RoutineAction


class RoutineRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_routines(self) -> list[Routine]:
        return self.db.query(Routine).order_by(Routine.created_at.desc()).all()

    def list_routine_actions(self) -> list[RoutineAction]:
        return self.db.query(RoutineAction).order_by(RoutineAction.id.desc()).all()

    def create_routine(self, name: str, cron_expression: str = "") -> Routine:
        routine = Routine(name=name, cron_expression=cron_expression)
        self.db.add(routine)
        self.db.commit()
        self.db.refresh(routine)
        return routine

    def create_routine_action(
        self,
        routine_id: int,
        module_id: int,
        execution_order: int = 1,
    ) -> RoutineAction:
        routine_action = RoutineAction(
            routine_id=routine_id,
            module_id=module_id,
            execution_order=execution_order,
        )
        self.db.add(routine_action)
        self.db.commit()
        self.db.refresh(routine_action)
        return routine_action
