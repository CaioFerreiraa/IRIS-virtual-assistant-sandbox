from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock


@dataclass(frozen=True)
class InvalidModuleInfo:
    folder_name: str
    message: str
    log_path: str
    module_public_key: str | None = None
    parent_public_key: str | None = None


@dataclass(frozen=True)
class ModuleRegistryState:
    invalid_modules: tuple[InvalidModuleInfo, ...] = ()
    synced_module_ids: tuple[int, ...] = ()
    runtime_statuses: dict[int, str] = field(default_factory=dict)
    readme_contents: dict[int, str] = field(default_factory=dict)


class ModuleRegistryStateStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._invalid_modules: tuple[InvalidModuleInfo, ...] = ()
        self._synced_module_ids: tuple[int, ...] = ()
        self._runtime_statuses: dict[int, str] = {}
        self._readme_contents: dict[int, str] = {}

    def replace_registry_result(
        self,
        invalid_modules: tuple[InvalidModuleInfo, ...],
        synced_module_ids: tuple[int, ...],
        readme_contents: dict[int, str] | None = None,
    ) -> None:
        with self._lock:
            self._invalid_modules = invalid_modules
            self._synced_module_ids = synced_module_ids
            self._readme_contents = dict(readme_contents or {})

    def set_runtime_status(self, module_id: int, status: str) -> None:
        with self._lock:
            self._runtime_statuses[module_id] = status

    def snapshot(self) -> ModuleRegistryState:
        with self._lock:
            return ModuleRegistryState(
                invalid_modules=self._invalid_modules,
                synced_module_ids=self._synced_module_ids,
                runtime_statuses=dict(self._runtime_statuses),
                readme_contents=dict(self._readme_contents),
            )


module_registry_state_store = ModuleRegistryStateStore()


def get_module_registry_state() -> ModuleRegistryState:
    return module_registry_state_store.snapshot()
