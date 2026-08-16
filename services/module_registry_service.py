from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from database.db import SessionLocal
from database.models import Module, ModuleVariableDefinition
from services.module_error_log import append_module_error_log
from services.module_loader import load_python_entrypoint
from services.module_manifest import (
    ManifestValidationError,
    ModuleManifest,
    parse_module_manifest,
)
from services.module_registry_state import (
    InvalidModuleInfo,
    ModuleRegistryState,
    get_module_registry_state,
    module_registry_state_store,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTALLED_MODULES_DIR = PROJECT_ROOT / "modules" / "installed"
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Candidate:
    manifest: ModuleManifest
    loaded_module: object | None
    readme_content: str


class ModuleRegistryService:
    def __init__(
        self,
        installed_modules_dir: Path = INSTALLED_MODULES_DIR,
        session_factory=SessionLocal,
    ) -> None:
        self.installed_modules_dir = installed_modules_dir.resolve()
        self.session_factory = session_factory
        self._invalid_modules: list[InvalidModuleInfo] = []

    def sync(self) -> ModuleRegistryState:
        self._invalid_modules = []
        candidates = self._discover_candidates()
        valid_candidates = self._validate_registry(candidates)
        synced_ids, synced_keys, readme_contents = self._sync_candidates(valid_candidates)
        self._mark_missing_modules_unavailable(synced_keys)
        module_registry_state_store.replace_registry_result(
            tuple(self._invalid_modules),
            tuple(synced_ids),
            readme_contents,
        )
        return get_module_registry_state()

    def _discover_candidates(self) -> list[_Candidate]:
        if not self.installed_modules_dir.is_dir():
            return []

        candidates: list[_Candidate] = []
        for folder in sorted(self.installed_modules_dir.iterdir(), key=lambda path: path.name.casefold()):
            if not folder.is_dir():
                continue
            try:
                data = self._load_json(folder)
                manifest = parse_module_manifest(data, folder)
                readme_content = manifest.readme_path.read_text(encoding="utf-8")
            except Exception as error:
                self._record_invalid(folder, "validação do manifesto", error)
                continue

            try:
                loaded_module = self._validate_import(manifest)
            except Exception as error:
                self._record_invalid(
                    folder,
                    "importação",
                    error,
                    module_public_key=manifest.module_public_key,
                )
                continue

            try:
                self._validate_runtime_contract(manifest, loaded_module)
            except Exception as error:
                self._record_invalid(
                    folder,
                    "configuração",
                    error,
                    module_public_key=manifest.module_public_key,
                )
                continue

            candidates.append(_Candidate(manifest, loaded_module, readme_content))
        return candidates

    def _load_json(self, folder: Path) -> object:
        manifest_path = folder / "module.json"
        if not manifest_path.is_file():
            raise ManifestValidationError("O arquivo module.json não foi encontrado.")
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ManifestValidationError("O arquivo module.json contém JSON inválido.") from error

    def _validate_import(self, manifest: ModuleManifest):
        if manifest.entrypoint_path is None:
            return None
        return load_python_entrypoint(
            manifest.entrypoint_path,
            manifest.module_public_key,
        )

    def _validate_runtime_contract(self, manifest: ModuleManifest, loaded_module) -> None:
        if loaded_module is None:
            return
        if manifest.is_executable and not any(
            callable(getattr(loaded_module, function_name, None))
            for function_name in ("execute", "run", "main")
        ):
            raise ManifestValidationError(
                "O entry point não possui uma função execute, run ou main."
            )
        if manifest.supports_auto_start and not callable(
            getattr(loaded_module, "start", None)
        ):
            raise ManifestValidationError(
                "Um runtime com auto start precisa fornecer a função start()."
            )

    def _validate_registry(self, candidates: list[_Candidate]) -> list[_Candidate]:
        candidates_by_key: dict[str, list[_Candidate]] = defaultdict(list)
        for candidate in candidates:
            candidates_by_key[candidate.manifest.module_public_key].append(candidate)

        invalid_keys: set[str] = set()
        for public_key, duplicates in candidates_by_key.items():
            if len(duplicates) < 2:
                continue
            invalid_keys.add(public_key)
            for duplicate in duplicates:
                self._record_validation_error(
                    duplicate.manifest,
                    f"A chave pública '{public_key}' está duplicada em modules/installed.",
                )

        unique_candidates = {
            public_key: values[0]
            for public_key, values in candidates_by_key.items()
            if public_key not in invalid_keys
        }
        existing_modules = self._load_existing_modules()

        for public_key, candidate in unique_candidates.items():
            existing = existing_modules.get(public_key)
            if existing is not None and existing.manifest_directory is None:
                invalid_keys.add(public_key)
                self._record_validation_error(
                    candidate.manifest,
                    f"A chave pública '{public_key}' já pertence a um módulo registrado.",
                )

        available_parent_keys = {
            key for key, module in existing_modules.items() if module.is_available
        }.union(unique_candidates)
        for public_key, candidate in unique_candidates.items():
            parent_key = candidate.manifest.parent_public_key
            if parent_key is not None and parent_key not in available_parent_keys:
                invalid_keys.add(public_key)
                self._record_validation_error(
                    candidate.manifest,
                    f"O módulo pai '{parent_key}' não foi encontrado.",
                )
            if parent_key is not None and candidate.manifest.supports_auto_start:
                invalid_keys.add(public_key)
                self._record_validation_error(
                    candidate.manifest,
                    "Módulos filhos não podem declarar auto start próprio.",
                )

        for cycle_key in self._find_cycle_keys(unique_candidates):
            if cycle_key in invalid_keys:
                continue
            invalid_keys.add(cycle_key)
            self._record_validation_error(
                unique_candidates[cycle_key].manifest,
                "Foi detectado um ciclo na hierarquia de módulos.",
            )

        changed = True
        while changed:
            changed = False
            for public_key, candidate in unique_candidates.items():
                parent_key = candidate.manifest.parent_public_key
                if public_key not in invalid_keys and parent_key in invalid_keys:
                    invalid_keys.add(public_key)
                    changed = True
                    self._record_validation_error(
                        candidate.manifest,
                        f"O módulo pai '{parent_key}' está inválido.",
                    )

        return [
            candidate
            for key, candidate in unique_candidates.items()
            if key not in invalid_keys
        ]

    def _load_existing_modules(self) -> dict[str, Module]:
        db: Session = self.session_factory()
        try:
            return {module.module_public_key: module for module in db.query(Module).all()}
        finally:
            db.close()

    def _find_cycle_keys(self, candidates: dict[str, _Candidate]) -> set[str]:
        cycle_keys: set[str] = set()
        visited: set[str] = set()

        for start_key in candidates:
            if start_key in visited:
                continue
            path: list[str] = []
            positions: dict[str, int] = {}
            current_key: str | None = start_key
            while current_key in candidates and current_key not in visited:
                if current_key in positions:
                    cycle_keys.update(path[positions[current_key] :])
                    break
                positions[current_key] = len(path)
                path.append(current_key)
                current_key = candidates[current_key].manifest.parent_public_key
            visited.update(path)
        return cycle_keys

    def _sync_candidates(
        self,
        candidates: list[_Candidate],
    ) -> tuple[list[int], set[str], dict[int, str]]:
        pending = {candidate.manifest.module_public_key: candidate for candidate in candidates}
        synced_ids: list[int] = []
        synced_keys: set[str] = set()
        readme_contents: dict[int, str] = {}

        while pending:
            progress = False
            for public_key, candidate in tuple(pending.items()):
                parent_key = candidate.manifest.parent_public_key
                if parent_key in pending:
                    continue
                try:
                    module_id = self._sync_candidate(candidate)
                except Exception as error:
                    self._record_invalid(
                        candidate.manifest.folder,
                        "configuração",
                        error,
                        module_public_key=public_key,
                    )
                else:
                    synced_ids.append(module_id)
                    synced_keys.add(public_key)
                    readme_contents[module_id] = candidate.readme_content
                pending.pop(public_key)
                progress = True
            if not progress:
                break
        return synced_ids, synced_keys, readme_contents

    def _sync_candidate(self, candidate: _Candidate) -> int:
        manifest = candidate.manifest
        db: Session = self.session_factory()
        try:
            module = (
                db.query(Module)
                .filter(Module.module_public_key == manifest.module_public_key)
                .one_or_none()
            )
            parent = None
            if manifest.parent_public_key is not None:
                parent = (
                    db.query(Module)
                    .filter(Module.module_public_key == manifest.parent_public_key)
                    .one_or_none()
                )
                if parent is None or not parent.is_available:
                    raise ManifestValidationError(
                        f"O módulo pai '{manifest.parent_public_key}' não está disponível."
                    )

            if module is None:
                module = Module(
                    module_public_key=manifest.module_public_key,
                    name=manifest.name,
                    call_name=manifest.call_name,
                )
                db.add(module)

            module.name = manifest.name
            module.call_name = manifest.call_name
            module.description = manifest.description
            module.parent_module_id = parent.id if parent is not None else None
            module.request_method = "PYTHON" if manifest.runtime_type else None
            module.request_url = (
                str(manifest.entrypoint_path)
                if manifest.entrypoint_path is not None
                else None
            )
            module.is_executable = manifest.is_executable
            module.is_available = True
            module.validation_error = None
            module.manifest_directory = str(manifest.folder)
            module.readme_path = str(manifest.readme_path)
            module.runtime_type = manifest.runtime_type
            module.supports_auto_start = manifest.supports_auto_start
            db.flush()
            self._sync_variable_definitions(db, module, manifest)
            db.commit()
            return int(module.id)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _sync_variable_definitions(
        self,
        db: Session,
        module: Module,
        manifest: ModuleManifest,
    ) -> None:
        existing_definitions = {
            definition.key: definition
            for definition in db.query(ModuleVariableDefinition)
            .filter(ModuleVariableDefinition.module_id == module.id)
            .all()
        }
        for definition in existing_definitions.values():
            definition.is_active = False

        for variable in manifest.variables:
            definition = existing_definitions.get(variable.key)
            if definition is None:
                definition = ModuleVariableDefinition(
                    module_id=module.id,
                    key=variable.key,
                )
                db.add(definition)
            definition.label = variable.label
            definition.description = variable.description
            definition.type = variable.type
            definition.is_required = variable.required
            definition.is_user_editable = variable.user_editable
            definition.default_value = variable.default_value
            definition.display_order = variable.display_order
            definition.is_active = True

    def _mark_missing_modules_unavailable(self, synced_keys: set[str]) -> None:
        db: Session = self.session_factory()
        try:
            managed_modules = (
                db.query(Module)
                .filter(Module.manifest_directory.is_not(None))
                .all()
            )
            invalid_messages = {
                item.module_public_key: item.message
                for item in self._invalid_modules
                if item.module_public_key
            }
            for module in managed_modules:
                if module.module_public_key in synced_keys:
                    continue
                module.is_available = False
                message = invalid_messages.get(module.module_public_key)
                module.validation_error = message[:255] if message else None
            db.commit()
        except Exception:
            db.rollback()
            LOGGER.exception("Não foi possível atualizar módulos ausentes ou inválidos.")
        finally:
            db.close()

    def _record_validation_error(self, manifest: ModuleManifest, message: str) -> None:
        try:
            raise ManifestValidationError(message)
        except ManifestValidationError as error:
            self._record_invalid(
                manifest.folder,
                "validação do manifesto",
                error,
                module_public_key=manifest.module_public_key,
            )

    def _record_invalid(
        self,
        folder: Path,
        stage: str,
        error: Exception,
        module_public_key: str | None = None,
    ) -> None:
        message = str(error).strip() or "O módulo apresentou um erro técnico."
        log_path = append_module_error_log(folder, stage, error)
        self._invalid_modules.append(
            InvalidModuleInfo(
                folder_name=folder.name,
                message=message,
                log_path=str(log_path.resolve()),
                module_public_key=module_public_key,
            )
        )

def initialize_module_registry() -> ModuleRegistryState:
    try:
        return ModuleRegistryService().sync()
    except Exception:
        LOGGER.exception("A descoberta de módulos falhou sem interromper a IRIS.")
        return get_module_registry_state()
