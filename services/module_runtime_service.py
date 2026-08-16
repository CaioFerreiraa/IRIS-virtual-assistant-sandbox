from __future__ import annotations

import inspect
import logging
from pathlib import Path
from threading import RLock, Thread

from sqlalchemy.orm import Session

from database.db import SessionLocal
from database.models import Module
from services.module_error_log import append_module_error_log
from services.module_loader import load_python_entrypoint
from services.module_registry_state import module_registry_state_store
from services.module_service import get_effective_module_variables


LOGGER = logging.getLogger(__name__)


class ModuleRuntimeManager:
    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory
        self._lock = RLock()
        self._threads: dict[int, Thread] = {}
        self._loaded_modules: dict[int, object] = {}
        self._owned_processes: dict[int, object] = {}

    def start_enabled_backends(self) -> None:
        db: Session = self.session_factory()
        try:
            backend_ids = [
                module_id
                for (module_id,) in db.query(Module.id)
                .filter(
                    Module.parent_module_id.is_(None),
                    Module.is_available.is_(True),
                    Module.runtime_type == "python",
                    Module.supports_auto_start.is_(True),
                    Module.auto_start_enabled.is_(True),
                )
                .all()
            ]
        finally:
            db.close()

        for module_id in backend_ids:
            with self._lock:
                current_thread = self._threads.get(module_id)
                if current_thread is not None and current_thread.is_alive():
                    continue
                thread = Thread(
                    target=self._start_backend,
                    args=(module_id,),
                    daemon=True,
                    name=f"iris-module-{module_id}",
                )
                self._threads[module_id] = thread
                thread.start()

    def _start_backend(self, module_id: int) -> None:
        module_registry_state_store.set_runtime_status(module_id, "iniciando")
        module_folder: Path | None = None
        try:
            db: Session = self.session_factory()
            try:
                module = db.query(Module).filter(Module.id == module_id).one_or_none()
                if module is None or not module.is_available:
                    return
                entrypoint = module.request_url or ""
                public_key = module.module_public_key
                module_folder = (
                    Path(module.manifest_directory)
                    if module.manifest_directory
                    else None
                )
                variables = get_effective_module_variables(db, module_id)
            finally:
                db.close()

            loaded_module = load_python_entrypoint(entrypoint, public_key)
            start_function = getattr(loaded_module, "start", None)
            if not callable(start_function):
                raise RuntimeError("O backend não fornece a função start().")
            handle = self._call_start(start_function, variables)
            with self._lock:
                self._loaded_modules[module_id] = loaded_module
                if self._is_process_handle(handle):
                    self._owned_processes[module_id] = handle
            module_registry_state_store.set_runtime_status(module_id, "online")
        except Exception as error:
            if module_folder is not None:
                append_module_error_log(module_folder, "inicialização", error)
            else:
                LOGGER.exception(
                    "Falha ao iniciar módulo sem pasta de manifesto: %s.",
                    module_id,
                )
            self._mark_initialization_failure(module_id, error)
            module_registry_state_store.set_runtime_status(module_id, "com erro")

    def _call_start(self, start_function, variables: dict[str, str]):
        signature = inspect.signature(start_function)
        accepts_variables = "variables" in signature.parameters or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
        return start_function(variables=variables) if accepts_variables else start_function()

    def _mark_initialization_failure(self, module_id: int, error: Exception) -> None:
        db: Session = self.session_factory()
        try:
            module = db.query(Module).filter(Module.id == module_id).one_or_none()
            if module is not None:
                module.is_available = False
                module.validation_error = (
                    str(error).strip() or "Falha ao iniciar o backend."
                )[:255]
                db.commit()
        except Exception:
            db.rollback()
            LOGGER.exception("Não foi possível marcar o backend %s como inválido.", module_id)
        finally:
            db.close()

    def shutdown(self) -> None:
        with self._lock:
            loaded_modules = dict(self._loaded_modules)
            owned_processes = dict(self._owned_processes)

        for module_id, loaded_module in loaded_modules.items():
            stop_function = getattr(loaded_module, "stop", None)
            if callable(stop_function):
                try:
                    stop_function()
                except Exception:
                    LOGGER.exception("Falha ao encerrar o módulo %s.", module_id)

        for module_id, process in owned_processes.items():
            try:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
            except Exception:
                LOGGER.exception("Falha ao encerrar o processo do módulo %s.", module_id)

        with self._lock:
            self._loaded_modules.clear()
            self._owned_processes.clear()

    def _is_process_handle(self, value: object) -> bool:
        return all(callable(getattr(value, attribute, None)) for attribute in ("poll", "terminate", "wait"))


module_runtime_manager = ModuleRuntimeManager()
