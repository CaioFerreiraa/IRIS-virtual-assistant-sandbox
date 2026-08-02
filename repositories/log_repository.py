from sqlalchemy.orm import Session

from database.models import Log


class LogRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_logs(self) -> list[Log]:
        return (
            self.db.query(Log)
            .outerjoin(Log.module)
            .outerjoin(Log.routine)
            .order_by(Log.created_at.desc())
            .all()
        )

    def create_log(
        self,
        module_id: int,
        status: str,
        message: str = "",
        routine_id: int | None = None,
    ) -> Log:
        log = Log(
            module_id=module_id,
            routine_id=routine_id,
            status=status,
            message=message,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log
