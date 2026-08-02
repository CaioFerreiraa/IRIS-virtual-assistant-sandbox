from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.logger_service import LoggerService
from database.db import get_db
from repositories.log_repository import LogRepository

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/")
def list_logs(db: Session = Depends(get_db)):
    return LogRepository(db).list_logs()


@router.post("/")
def create_log(
    module_id: int,
    status: str,
    message: str = "",
    routine_id: int | None = None,
    db: Session = Depends(get_db),
):
    logger = LoggerService(LogRepository(db))
    return logger.create_log(
        module_id=module_id,
        status=status.strip(),
        message=message.strip(),
        routine_id=routine_id,
    )
