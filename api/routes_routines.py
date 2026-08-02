from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.routine_executor import RoutineExecutor
from database.db import get_db
from repositories.routine_repository import RoutineRepository

router = APIRouter(prefix="/routines", tags=["routines"])


@router.get("/")
def list_routines(db: Session = Depends(get_db)):
    return RoutineRepository(db).list_routines()


@router.post("/")
def create_routine(name: str, cron_expression: str = "", db: Session = Depends(get_db)):
    executor = RoutineExecutor(RoutineRepository(db))
    return executor.create_routine(
        name=name.strip(),
        cron_expression=cron_expression.strip(),
    )
