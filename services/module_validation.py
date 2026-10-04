from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import ModuleType

from services.module_loader import load_python_entrypoint
from services.module_manifest import (
    ManifestValidationError,
    ModuleManifest,
    parse_module_manifest,
)


@dataclass(frozen=True)
class ValidatedModule:
    manifest: ModuleManifest
    loaded_module: ModuleType | None
    readme_content: str


class ModuleFolderValidationError(ValueError):
    def __init__(
        self,
        stage: str,
        error: Exception,
        *,
        module_public_key: str | None = None,
        parent_public_key: str | None = None,
    ) -> None:
        self.stage = stage
        self.error = error
        self.module_public_key = module_public_key
        self.parent_public_key = parent_public_key
        super().__init__(str(error).strip() or "O módulo apresentou um erro técnico.")


def validate_module_folder(
    folder: Path,
    *,
    check_runtime: bool = False,
) -> ValidatedModule:
    resolved_folder = folder.resolve()
    data: object = None
    try:
        data = _load_manifest_data(resolved_folder)
        manifest = parse_module_manifest(data, resolved_folder)
        readme_content = manifest.readme_path.read_text(encoding="utf-8")
    except Exception as error:
        module_public_key, parent_public_key = _extract_manifest_identity(data)
        raise ModuleFolderValidationError(
            "validação do manifesto",
            error,
            module_public_key=module_public_key,
            parent_public_key=parent_public_key,
        ) from error

    loaded_module = None
    if check_runtime and manifest.entrypoint_path is not None:
        try:
            loaded_module = load_python_entrypoint(
                manifest.entrypoint_path,
                manifest.module_public_key,
            )
        except Exception as error:
            raise ModuleFolderValidationError(
                "importação",
                error,
                module_public_key=manifest.module_public_key,
                parent_public_key=manifest.parent_public_key,
            ) from error

        try:
            validate_runtime_contract(manifest, loaded_module)
        except Exception as error:
            raise ModuleFolderValidationError(
                "configuração",
                error,
                module_public_key=manifest.module_public_key,
                parent_public_key=manifest.parent_public_key,
            ) from error

    return ValidatedModule(manifest, loaded_module, readme_content)


def validate_runtime_contract(
    manifest: ModuleManifest,
    loaded_module: ModuleType | None,
) -> None:
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


def _load_manifest_data(folder: Path) -> object:
    manifest_path = folder / "module.json"
    if not manifest_path.is_file():
        raise ManifestValidationError("O arquivo module.json não foi encontrado.")
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ManifestValidationError(
            "O arquivo module.json contém JSON inválido."
        ) from error


def _extract_manifest_identity(data: object) -> tuple[str | None, str | None]:
    if not isinstance(data, dict):
        return None, None
    module_data = data.get("module")
    if not isinstance(module_data, dict):
        return None, None
    module_public_key = module_data.get("module_public_key")
    parent_public_key = module_data.get("parent_public_key")
    return (
        module_public_key if isinstance(module_public_key, str) else None,
        parent_public_key if isinstance(parent_public_key, str) else None,
    )
