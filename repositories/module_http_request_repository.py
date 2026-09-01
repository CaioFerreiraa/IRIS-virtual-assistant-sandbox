from sqlalchemy.orm import Session

from database.models import ModuleHttpRequest


class ModuleHttpRequestRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_module_id(self, module_id: int) -> ModuleHttpRequest | None:
        return (
            self.db.query(ModuleHttpRequest)
            .filter(ModuleHttpRequest.module_id == module_id)
            .one_or_none()
        )
