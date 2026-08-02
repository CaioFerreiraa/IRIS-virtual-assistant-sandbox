from repositories.log_repository import LogRepository


class LoggerService:
    def __init__(self, log_repository: LogRepository):
        self.log_repository = log_repository

    def create_log(
        self,
        module_id: int | None,
        status: str,
        message: str = "",
        routine_id: int | None = None,
    ):
        if module_id is None or not status:
            raise ValueError("Preencha module_id e status.")
        return self.log_repository.create_log(
            module_id=module_id,
            status=status,
            message=message,
            routine_id=routine_id,
        )
