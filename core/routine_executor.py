from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import threading

from sqlalchemy.orm import Session, sessionmaker

from core.command_processor import CommandProcessor
from database.db import SessionLocal
from repositories.module_repository import ModuleRepository
from repositories.routine_repository import RoutineRepository


ProcessorFactory = Callable[[Session], CommandProcessor]


class RoutineExecutor:
    _running_routine_ids: set[int] = set()
    _running_lock = threading.Lock()

    def __init__(
        self,
        session_factory=SessionLocal,
        processor_factory: ProcessorFactory | None = None,
    ) -> None:
        if isinstance(session_factory, RoutineRepository):
            session_factory = sessionmaker(bind=session_factory.db.get_bind())
        self.session_factory = session_factory
        self.processor_factory = processor_factory or self._build_processor

    def execute(self, routine_id: int) -> dict[str, object]:
        if not self._acquire(routine_id):
            return self._busy_result(routine_id)

        db: Session = self.session_factory()
        try:
            repository = RoutineRepository(db)
            routine = repository.get_by_id(routine_id)
            if routine is None:
                return self._error_result(
                    routine_id,
                    "A rotina não foi encontrada ou já foi excluída.",
                )

            actions = sorted(
                (
                    action
                    for action in routine.routine_actions
                    if bool(action.active)
                ),
                key=lambda action: (action.execution_order, action.id),
            )
            step_results: list[dict[str, object]] = []
            successes = 0
            failures = 0
            interrupted = False
            processor = self.processor_factory(db)

            for index, action in enumerate(actions):
                step_result = self._execute_action(
                    processor,
                    routine_id,
                    action,
                )
                step_results.append(step_result)
                if step_result["status"] == "success":
                    successes += 1
                    continue

                failures += 1
                if bool(routine.stop_on_failure):
                    interrupted = True
                    for pending_action in actions[index + 1 :]:
                        step_results.append(
                            self._skipped_step_result(pending_action)
                        )
                    break

            repository.update_last_run(routine, datetime.now())
            db.commit()
            return self._build_result(
                routine_id=routine_id,
                total=len(actions),
                successes=successes,
                failures=failures,
                interrupted=interrupted,
                steps=step_results,
            )
        except Exception as error:
            db.rollback()
            try:
                routine = RoutineRepository(db).get_by_id(routine_id)
                if routine is not None:
                    RoutineRepository(db).update_last_run(routine, datetime.now())
                    db.commit()
            except Exception:
                db.rollback()
            return self._error_result(
                routine_id,
                str(error).strip() or "Não foi possível executar a rotina.",
            )
        finally:
            db.close()
            self._release(routine_id)

    def is_running(self, routine_id: int) -> bool:
        with self._running_lock:
            return routine_id in self._running_routine_ids

    def _build_processor(self, db: Session) -> CommandProcessor:
        return CommandProcessor(ModuleRepository(db), self.session_factory)

    def _execute_action(
        self,
        processor: CommandProcessor,
        routine_id: int,
        action,
    ) -> dict[str, object]:
        module = action.module
        module_name = module.name if module is not None else "Módulo indisponível"
        base_result = {
            "action_id": action.id,
            "module_id": action.module_id,
            "module": module_name,
            "execution_order": action.execution_order,
        }
        if module is None:
            return {
                **base_result,
                "status": "error",
                "success": False,
                "message": "O módulo desta etapa não existe mais.",
            }
        if not bool(module.is_available):
            message = "O módulo desta etapa está indisponível."
            try:
                processor.execute_module_id(
                    action.module_id,
                    action.argument,
                    routine_id=routine_id,
                )
            except Exception as error:
                message = str(error).strip() or message
            return {
                **base_result,
                "status": "error",
                "success": False,
                "message": message,
            }
        if not bool(module.is_executable):
            message = "O módulo desta etapa não é mais executável."
            try:
                processor.execute_module_id(
                    action.module_id,
                    action.argument,
                    routine_id=routine_id,
                )
            except Exception as error:
                message = str(error).strip() or message
            return {
                **base_result,
                "status": "error",
                "success": False,
                "message": message,
            }

        try:
            result = processor.execute_module_id(
                action.module_id,
                action.argument,
                routine_id=routine_id,
            )
        except Exception as error:
            return {
                **base_result,
                "status": "error",
                "success": False,
                "message": str(error).strip() or "A etapa falhou durante a execução.",
            }

        success = bool(result.get("success", True))
        return {
            **base_result,
            "status": "success" if success else "error",
            "success": success,
            "message": self._result_message(result, success),
        }

    def _skipped_step_result(self, action) -> dict[str, object]:
        module_name = (
            action.module.name
            if action.module is not None
            else "Módulo indisponível"
        )
        return {
            "action_id": action.id,
            "module_id": action.module_id,
            "module": module_name,
            "execution_order": action.execution_order,
            "status": "skipped",
            "success": False,
            "message": "Etapa não executada após uma falha anterior.",
        }

    def _build_result(
        self,
        *,
        routine_id: int,
        total: int,
        successes: int,
        failures: int,
        interrupted: bool,
        steps: list[dict[str, object]],
    ) -> dict[str, object]:
        executed = successes + failures
        if failures == 0 and successes == total and total > 0:
            status = "success"
            message = "Rotina executada com sucesso."
        elif failures > 0 and successes > 0:
            status = "partial"
            message = "A rotina foi concluída parcialmente."
        else:
            status = "error"
            message = (
                "A rotina não possui etapas ativas."
                if total == 0
                else "Não foi possível concluir a rotina."
            )
        return {
            "success": status == "success",
            "routine_id": routine_id,
            "status": status,
            "total": total,
            "executed": executed,
            "failures": failures,
            "skipped": total - executed,
            "interrupted": interrupted,
            "already_running": False,
            "message": message,
            "steps": steps,
        }

    def _busy_result(self, routine_id: int) -> dict[str, object]:
        return {
            "success": False,
            "routine_id": routine_id,
            "status": "error",
            "total": 0,
            "executed": 0,
            "failures": 0,
            "skipped": 0,
            "interrupted": False,
            "already_running": True,
            "message": "Esta rotina já está em execução.",
            "steps": [],
        }

    def _error_result(self, routine_id: int, message: str) -> dict[str, object]:
        result = self._busy_result(routine_id)
        result["already_running"] = False
        result["message"] = message
        return result

    def _result_message(self, result: dict, success: bool) -> str:
        for key in ("message", "result"):
            if key in result and result[key] is not None:
                return str(result[key])
        if "opened" in result:
            return "Recurso aberto com sucesso."
        return "Etapa concluída." if success else "A etapa retornou uma falha."

    @classmethod
    def _acquire(cls, routine_id: int) -> bool:
        with cls._running_lock:
            if routine_id in cls._running_routine_ids:
                return False
            cls._running_routine_ids.add(routine_id)
            return True

    @classmethod
    def _release(cls, routine_id: int) -> None:
        with cls._running_lock:
            cls._running_routine_ids.discard(routine_id)
