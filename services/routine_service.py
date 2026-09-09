from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from core.module_runner import PYTHON_REQUEST_METHOD, ModuleRunner
from core.routine_executor import RoutineExecutor
from database.db import SessionLocal
from repositories.module_repository import ModuleRepository
from repositories.routine_repository import RoutineRepository
from services.http_service import validate_non_sensitive_argument
from services.module_service import get_effective_module_variables
from services.routine_schedule_service import RoutineScheduleService

if TYPE_CHECKING:
    from services.routine_scheduler_service import RoutineSchedulerService


class RoutineService:
    def __init__(
        self,
        session_factory=SessionLocal,
        *,
        schedule_service: RoutineScheduleService | None = None,
        scheduler_service: RoutineSchedulerService | None = None,
        executor: RoutineExecutor | None = None,
        close_sessions: bool = True,
    ) -> None:
        self.session_factory = session_factory
        self.schedule_service = schedule_service or RoutineScheduleService()
        self.scheduler_service = scheduler_service
        self.executor = executor or RoutineExecutor(session_factory)
        self.close_sessions = close_sessions
        self.module_runner = ModuleRunner()

    def list_routines(self) -> list[dict[str, object]]:
        db = self.session_factory()
        try:
            repository = RoutineRepository(db)
            module_repository = ModuleRepository(db)
            return [
                self._serialize_routine(routine, module_repository)
                for routine in repository.list_routines()
            ]
        finally:
            self._close(db)

    def get_routine(self, routine_id: int) -> dict[str, object]:
        db = self.session_factory()
        try:
            routine = RoutineRepository(db).get_by_id(routine_id)
            if routine is None:
                raise ValueError("Rotina não encontrada.")
            return self._serialize_routine(routine, ModuleRepository(db))
        finally:
            self._close(db)

    def list_executable_modules(self) -> list[dict[str, object]]:
        db = self.session_factory()
        try:
            repository = ModuleRepository(db)
            result: list[dict[str, object]] = []
            for module in repository.list_modules(available_only=False):
                if not bool(module.is_executable):
                    continue
                accepts_argument, requires_argument = self._argument_context(
                    module,
                    repository,
                )
                result.append(
                    {
                        "module_id": module.id,
                        "path": repository.get_module_path(module),
                        "is_available": bool(module.is_available),
                        "accepts_argument": accepts_argument,
                        "requires_argument": requires_argument,
                        "validation_error": module.validation_error or "",
                    }
                )
            return result
        finally:
            self._close(db)

    def create_routine(
        self,
        *,
        name: str,
        schedule_type: str,
        days: Sequence[str | int],
        time_value: str,
        active: bool,
        stop_on_failure: bool,
        actions: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        normalized_name = self._validate_name(name)
        self._validate_boolean(active, "O estado da rotina")
        self._validate_boolean(
            stop_on_failure,
            "A opção de interrupção em falha",
        )
        cron_expression = self.schedule_service.build_cron(
            schedule_type,
            days,
            time_value,
        )

        db = self.session_factory()
        routine_id: int | None = None
        try:
            repository = RoutineRepository(db)
            module_repository = ModuleRepository(db)
            validated_actions = self._validate_actions(
                actions,
                module_repository,
                existing_actions={},
            )
            routine = repository.create_routine(
                normalized_name,
                cron_expression,
                active=active,
                stop_on_failure=stop_on_failure,
            )
            routine_id = routine.id
            for action in validated_actions:
                repository.create_routine_action(
                    routine.id,
                    action["module_id"],
                    action["execution_order"],
                    active=action["active"],
                    argument=action["argument"],
                )
            db.commit()
            saved = repository.get_by_id(routine.id)
            if saved is None:
                raise RuntimeError("A rotina salva não pôde ser recarregada.")
            result = self._serialize_routine(saved, module_repository)
        except Exception:
            db.rollback()
            raise
        finally:
            self._close(db)

        self._sync_scheduler(routine_id)
        return result

    def update_routine(
        self,
        routine_id: int,
        *,
        name: str,
        schedule_type: str,
        days: Sequence[str | int],
        time_value: str,
        active: bool,
        stop_on_failure: bool,
        actions: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        normalized_name = self._validate_name(name)
        self._validate_boolean(active, "O estado da rotina")
        self._validate_boolean(
            stop_on_failure,
            "A opção de interrupção em falha",
        )
        cron_expression = self.schedule_service.build_cron(
            schedule_type,
            days,
            time_value,
        )

        db = self.session_factory()
        try:
            repository = RoutineRepository(db)
            module_repository = ModuleRepository(db)
            routine = repository.get_by_id(routine_id)
            if routine is None:
                raise ValueError("Rotina não encontrada.")
            existing_actions = {
                action.id: action
                for action in routine.routine_actions
            }
            validated_actions = self._validate_actions(
                actions,
                module_repository,
                existing_actions=existing_actions,
            )

            routine.name = normalized_name
            routine.cron_expression = cron_expression
            routine.active = active
            routine.stop_on_failure = stop_on_failure

            retained_action_ids: set[int] = set()
            for action_values in validated_actions:
                action_id = action_values["action_id"]
                if action_id is None:
                    repository.create_routine_action(
                        routine.id,
                        action_values["module_id"],
                        action_values["execution_order"],
                        active=action_values["active"],
                        argument=action_values["argument"],
                    )
                    continue
                persisted_action = existing_actions[action_id]
                retained_action_ids.add(action_id)
                persisted_action.module_id = action_values["module_id"]
                persisted_action.execution_order = action_values["execution_order"]
                persisted_action.active = action_values["active"]
                persisted_action.argument = action_values["argument"]

            for action_id, persisted_action in existing_actions.items():
                if action_id not in retained_action_ids:
                    repository.delete_action(persisted_action)

            db.commit()
            saved = repository.get_by_id(routine.id)
            if saved is None:
                raise RuntimeError("A rotina salva não pôde ser recarregada.")
            result = self._serialize_routine(saved, module_repository)
        except Exception:
            db.rollback()
            raise
        finally:
            self._close(db)

        self._sync_scheduler(routine_id)
        return result

    def set_active(self, routine_id: int, active: bool) -> dict[str, object]:
        self._validate_boolean(active, "O estado da rotina")
        db = self.session_factory()
        try:
            repository = RoutineRepository(db)
            routine = repository.get_by_id(routine_id)
            if routine is None:
                raise ValueError("Rotina não encontrada.")
            if active:
                self.schedule_service.parse_cron(routine.cron_expression)
            repository.set_active(routine, active)
            db.commit()
            result = self._serialize_routine(routine, ModuleRepository(db))
        except Exception:
            db.rollback()
            raise
        finally:
            self._close(db)

        self._sync_scheduler(routine_id)
        return result

    def delete_routine(self, routine_id: int) -> dict[str, object]:
        db = self.session_factory()
        try:
            repository = RoutineRepository(db)
            routine = repository.get_by_id(routine_id)
            if routine is None:
                raise ValueError("Rotina não encontrada.")
            repository.soft_delete(routine, datetime.now())
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            self._close(db)

        self._remove_scheduler_job(routine_id)
        return {
            "success": True,
            "routine_id": routine_id,
            "message": "Rotina excluída com sucesso.",
        }

    def execute_manual(self, routine_id: int) -> dict[str, object]:
        return self.executor.execute(routine_id)

    def _validate_actions(
        self,
        actions: Sequence[Mapping[str, object]],
        module_repository: ModuleRepository,
        *,
        existing_actions: Mapping[int, object],
    ) -> list[dict[str, object]]:
        if not isinstance(actions, Sequence) or isinstance(actions, (str, bytes)):
            raise ValueError("Informe os módulos da rotina.")
        if not actions:
            raise ValueError("Adicione ao menos um módulo à rotina.")

        validated: list[dict[str, object]] = []
        seen_action_ids: set[int] = set()
        for execution_order, values in enumerate(actions, start=1):
            if not isinstance(values, Mapping):
                raise ValueError("Uma etapa da rotina possui formato inválido.")
            module_id = values.get("module_id")
            if type(module_id) is not int:
                raise ValueError("Selecione um módulo válido para cada etapa.")
            active = values.get("active", True)
            self._validate_boolean(active, "O estado da etapa")

            raw_action_id = values.get("action_id")
            action_id = raw_action_id if type(raw_action_id) is int else None
            if raw_action_id is not None and action_id is None:
                raise ValueError("Uma etapa salva possui identificador inválido.")
            if action_id is not None:
                if action_id in seen_action_ids or action_id not in existing_actions:
                    raise ValueError("Uma etapa salva não pertence a esta rotina.")
                seen_action_ids.add(action_id)

            existing_action = (
                existing_actions.get(action_id)
                if action_id is not None
                else None
            )
            preserves_existing_module = bool(
                existing_action is not None
                and existing_action.module_id == module_id
            )
            module = module_repository.get_by_id(module_id)
            if module is None and not preserves_existing_module:
                raise ValueError("Um dos módulos informados não existe.")
            if (
                module is not None
                and not bool(module.is_executable)
                and not preserves_existing_module
            ):
                raise ValueError("Somente módulos executáveis podem entrar em uma rotina.")
            if (
                module is not None
                and not bool(module.is_available)
                and not preserves_existing_module
            ):
                raise ValueError("Módulos indisponíveis não podem ser adicionados à rotina.")

            raw_argument = values.get("argument")
            if raw_argument is not None and not isinstance(raw_argument, str):
                raise ValueError("O argumento da etapa deve conter texto.")
            normalized_argument = (
                raw_argument.strip()
                if isinstance(raw_argument, str)
                else None
            )
            validate_non_sensitive_argument(normalized_argument)

            accepts_argument = False
            requires_argument = False
            if module is not None and bool(module.is_available):
                accepts_argument, requires_argument = self._argument_context(
                    module,
                    module_repository,
                )
            elif preserves_existing_module:
                accepts_argument = bool(
                    normalized_argument
                    or getattr(existing_action, "argument", None)
                    or (
                        module is not None
                        and module.http_request is not None
                        and module.http_request.argument_enabled
                    )
                )

            if not accepts_argument and normalized_argument:
                raise ValueError("O módulo selecionado não aceita argumento.")
            if requires_argument and not normalized_argument:
                module_name = module.name if module is not None else "selecionado"
                raise ValueError(
                    f"Informe o argumento obrigatório do módulo '{module_name}'."
                )

            validated.append(
                {
                    "action_id": action_id,
                    "module_id": module_id,
                    "execution_order": execution_order,
                    "active": active,
                    "argument": normalized_argument or None,
                }
            )
        return validated

    def _argument_context(
        self,
        module,
        module_repository: ModuleRepository,
    ) -> tuple[bool, bool]:
        if module.http_request is not None:
            accepts_argument = bool(module.http_request.argument_enabled)
            return accepts_argument, accepts_argument
        if (
            (module.request_method or "").upper() != PYTHON_REQUEST_METHOD
            or not module.request_url
            or not bool(module.is_available)
        ):
            return False, False
        try:
            accepts_argument = self.module_runner.has_argument_search(
                module.request_url,
                module.module_public_key,
            )
            if not accepts_argument:
                return False, False
            variables = get_effective_module_variables(
                module_repository.db,
                module.id,
            )
            requires_argument = self.module_runner.should_request_argument(
                module.request_url,
                variables,
                module.module_public_key,
            )
            return True, bool(requires_argument)
        except Exception:
            return False, False

    def _serialize_routine(
        self,
        routine,
        module_repository: ModuleRepository,
    ) -> dict[str, object]:
        schedule = self.schedule_service.inspect(routine.cron_expression)
        actions: list[dict[str, object]] = []
        for action in sorted(
            routine.routine_actions,
            key=lambda item: (item.execution_order, item.id),
        ):
            module = action.module
            accepts_argument = False
            requires_argument = False
            if module is not None:
                accepts_argument, requires_argument = self._argument_context(
                    module,
                    module_repository,
                )
            if action.argument:
                accepts_argument = True
            actions.append(
                {
                    "action_id": action.id,
                    "module_id": action.module_id,
                    "execution_order": action.execution_order,
                    "active": bool(action.active),
                    "argument": action.argument,
                    "module_path": (
                        module_repository.get_module_path(module)
                        if module is not None
                        else f"Módulo removido (ID {action.module_id})"
                    ),
                    "module_available": bool(
                        module is not None
                        and module.is_available
                        and module.is_executable
                    ),
                    "module_error": (
                        ""
                        if module is not None
                        and module.is_available
                        and module.is_executable
                        else (
                            module.validation_error
                            if module is not None and module.validation_error
                            else "Esta etapa está indisponível."
                        )
                    ),
                    "accepts_argument": accepts_argument,
                    "requires_argument": requires_argument,
                }
            )
        return {
            "id": routine.id,
            "name": routine.name,
            "cron_expression": routine.cron_expression or "",
            "active": bool(routine.active),
            "stop_on_failure": bool(routine.stop_on_failure),
            "last_run_at": routine.last_run_at,
            "created_at": routine.created_at,
            "deleted_at": routine.deleted_at,
            "schedule_valid": bool(schedule["valid"]),
            "schedule_type": schedule["schedule_type"],
            "days": schedule["days"],
            "time": schedule["time"],
            "schedule_description": schedule["description"],
            "schedule_error": schedule["error"],
            "next_run_at": schedule["next_run"] if routine.active else None,
            "module_count": len(actions),
            "actions": actions,
        }

    def _validate_name(self, name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Informe o nome da rotina.")
        normalized_name = name.strip()
        if len(normalized_name) > 100:
            raise ValueError("O nome da rotina aceita até 100 caracteres.")
        return normalized_name

    def _validate_boolean(self, value: object, label: str) -> None:
        if type(value) is not bool:
            raise ValueError(f"{label} deve ser booleano.")

    def _sync_scheduler(self, routine_id: int | None) -> None:
        if routine_id is None:
            return
        scheduler = self._get_scheduler()
        scheduler.sync_routine(routine_id)

    def _remove_scheduler_job(self, routine_id: int) -> None:
        self._get_scheduler().remove_routine(routine_id)

    def _get_scheduler(self):
        if self.scheduler_service is None:
            from services.routine_scheduler_service import routine_scheduler_service

            return routine_scheduler_service
        return self.scheduler_service

    def _close(self, db: Session) -> None:
        if self.close_sessions:
            db.close()
