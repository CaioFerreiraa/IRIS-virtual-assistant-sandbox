from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.db import get_db
from services.routine_service import RoutineService


router = APIRouter(prefix="/routines", tags=["routines"])


class RoutineActionPayload(BaseModel):
    action_id: int | None = None
    module_id: int
    argument: str | None = None
    active: bool = True


class RoutinePayload(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    schedule_type: str
    days: list[str | int]
    time: str
    active: bool = True
    stop_on_failure: bool = True
    actions: list[RoutineActionPayload]


class RoutineActivePayload(BaseModel):
    active: bool


@router.get("/")
def list_routines(db: Session = Depends(get_db)):
    return _service(db).list_routines()


@router.get("/modules")
def list_routine_modules(db: Session = Depends(get_db)):
    return _service(db).list_executable_modules()


@router.get("/{routine_id}")
def get_routine(routine_id: int, db: Session = Depends(get_db)):
    return _call(_service(db).get_routine, routine_id)


@router.post("/")
def create_routine(payload: RoutinePayload, db: Session = Depends(get_db)):
    return _call(
        _service(db).create_routine,
        **_payload_values(payload),
    )


@router.put("/{routine_id}")
def update_routine(
    routine_id: int,
    payload: RoutinePayload,
    db: Session = Depends(get_db),
):
    return _call(
        _service(db).update_routine,
        routine_id,
        **_payload_values(payload),
    )


@router.patch("/{routine_id}/active")
def set_routine_active(
    routine_id: int,
    payload: RoutineActivePayload,
    db: Session = Depends(get_db),
):
    return _call(_service(db).set_active, routine_id, payload.active)


@router.delete("/{routine_id}")
def delete_routine(routine_id: int, db: Session = Depends(get_db)):
    return _call(_service(db).delete_routine, routine_id)


@router.post("/{routine_id}/execute")
def execute_routine(routine_id: int, db: Session = Depends(get_db)):
    return _call(_service(db).execute_manual, routine_id)


def _service(db: Session) -> RoutineService:
    return RoutineService(lambda: db, close_sessions=False)


def _payload_values(payload: RoutinePayload) -> dict[str, Any]:
    return {
        "name": payload.name,
        "schedule_type": payload.schedule_type,
        "days": payload.days,
        "time_value": payload.time,
        "active": payload.active,
        "stop_on_failure": payload.stop_on_failure,
        "actions": [action.model_dump() for action in payload.actions],
    }


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except ValueError as error:
        message = str(error)
        status_code = 404 if "não encontrad" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from error
