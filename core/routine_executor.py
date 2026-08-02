from repositories.routine_repository import RoutineRepository


class RoutineExecutor:
    def __init__(self, routine_repository: RoutineRepository):
        self.routine_repository = routine_repository

    def create_routine(self, name: str, cron_expression: str = ""):
        if not name:
            raise ValueError("Informe o nome da rotina.")
        return self.routine_repository.create_routine(
            name=name,
            cron_expression=cron_expression,
        )

    def create_routine_action(
        self,
        routine_id: int | None,
        module_id: int | None,
        execution_order: int = 1,
    ):
        if routine_id is None or module_id is None:
            raise ValueError("Preencha routine_id e module_id.")
        return self.routine_repository.create_routine_action(
            routine_id=routine_id,
            module_id=module_id,
            execution_order=execution_order,
        )
