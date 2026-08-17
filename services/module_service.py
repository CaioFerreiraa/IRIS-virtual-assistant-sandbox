from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
import re

from sqlalchemy.orm import Session

from database.db import SessionLocal
from database.models import ModuleVariableValue
from repositories.module_repository import ModuleRepository
from services.module_registry_state import get_module_registry_state
from core.module_runner import ModuleRunner


def get_module_detail(
    module_id: int,
    session_factory=SessionLocal,
) -> dict[str, object] | None:
    db: Session = session_factory()
    try:
        repository = ModuleRepository(db)
        module = repository.get_by_id(module_id)
        if module is None:
            return None

        registry_state = get_module_registry_state()
        runtime_status = registry_state.runtime_statuses.get(module.id)
        status = _module_status(module.is_available, module.validation_error, runtime_status)
        variables = []
        for definition in repository.list_variable_definitions(module.id):
            persisted_value = repository.get_variable_value(definition.id)
            variables.append(
                {
                    "id": definition.id,
                    "key": definition.key,
                    "label": definition.label,
                    "description": definition.description or "",
                    "type": definition.type,
                    "required": bool(definition.is_required),
                    "user_editable": bool(definition.is_user_editable),
                    "default_value": definition.default_value,
                    "value": (
                        persisted_value.value_text
                        if persisted_value is not None
                        else definition.default_value or ""
                    ),
                }
            )

        readme_content, readme_error = _read_module_readme(
            module.manifest_directory,
            module.readme_path,
        )
        manifest_content, manifest_error = _read_module_manifest(
            module.manifest_directory,
        )
        technical_errors = _build_technical_errors(
            repository,
            module,
            registry_state.runtime_statuses,
            registry_state.invalid_modules,
        )
        if readme_error:
            technical_errors.append(
                _build_technical_error(module, readme_error)
            )
        if manifest_error:
            technical_errors.append(
                _build_technical_error(module, manifest_error)
            )
        has_arguments, argument_error = _detect_argument_capability(module)
        if argument_error:
            technical_errors.append(
                _build_technical_error(module, argument_error)
            )
        return {
            "id": module.id,
            "module_public_key": module.module_public_key,
            "name": module.name,
            "icon": module.icon or "extension",
            "call_name": module.call_name,
            "custom_call_name": module.custom_call_name or "",
            "description": module.description or "",
            "request_method": module.request_method or "",
            "request_url": module.request_url or "",
            "is_executable": bool(module.is_executable),
            "is_available": bool(module.is_available),
            "validation_error": module.validation_error or "",
            "status": status,
            "supports_auto_start": bool(module.supports_auto_start),
            "auto_start_enabled": bool(module.auto_start_enabled),
            "can_auto_start": bool(
                module.is_available
                and module.runtime_type == "python"
                and module.supports_auto_start
                and module.parent_module_id is None
            ),
            "breadcrumb": repository.get_breadcrumb(module),
            "readme_content": readme_content,
            "readme_error": readme_error,
            "manifest_content": manifest_content,
            "manifest_error": manifest_error,
            "has_arguments": has_arguments,
            "technical_errors": _deduplicate_errors(technical_errors),
            "model_data": _build_model_data(module),
            "variables": variables,
        }
    finally:
        db.close()


def save_custom_call_name(
    module_id: int,
    custom_call_name: str | None,
    session_factory=SessionLocal,
) -> None:
    normalized_value = _normalize_custom_call_name(custom_call_name)

    db: Session = session_factory()
    try:
        module = ModuleRepository(db).get_by_id(module_id)
        if module is None:
            raise ValueError("Módulo não encontrado.")
        module.custom_call_name = normalized_value or None
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def save_module_settings(
    module_id: int,
    custom_call_name: str | None,
    values: dict[str, str],
    session_factory=SessionLocal,
) -> None:
    normalized_custom_call_name = _normalize_custom_call_name(custom_call_name)
    db: Session = session_factory()
    try:
        repository = ModuleRepository(db)
        module = repository.get_by_id(module_id)
        if module is None:
            raise ValueError("Módulo não encontrado.")
        if not module.is_available:
            raise ValueError("O módulo está indisponível e não pode ser configurado.")

        definitions = {
            definition.key: definition
            for definition in repository.list_variable_definitions(module_id)
            if definition.is_user_editable
        }
        unknown_keys = set(values).difference(definitions)
        if unknown_keys:
            raise ValueError("Foram informadas configurações que não pertencem ao módulo.")

        for key, definition in definitions.items():
            value = values.get(key, "")
            if not isinstance(value, str):
                raise ValueError(f"O campo '{definition.label}' deve receber texto.")
            if definition.is_required and not value.strip():
                raise ValueError(f"Preencha o campo obrigatório '{definition.label}'.")

            persisted_value = repository.get_variable_value(definition.id)
            if persisted_value is None:
                db.add(
                    ModuleVariableValue(
                        variable_definition_id=definition.id,
                        value_text=value,
                    )
                )
            else:
                persisted_value.value_text = value

        module.custom_call_name = normalized_custom_call_name or None
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def save_auto_start_preference(
    module_id: int,
    enabled: bool,
    session_factory=SessionLocal,
) -> None:
    if type(enabled) is not bool:
        raise ValueError("A preferência de inicialização deve ser booleana.")

    db: Session = session_factory()
    try:
        module = ModuleRepository(db).get_by_id(module_id)
        if module is None:
            raise ValueError("Módulo não encontrado.")
        if not (
            module.is_available
            and module.runtime_type == "python"
            and module.supports_auto_start
            and module.parent_module_id is None
        ):
            raise ValueError("Este módulo não oferece inicialização automática.")
        module.auto_start_enabled = enabled
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def save_module_variable_values(
    module_id: int,
    values: dict[str, str],
    session_factory=SessionLocal,
) -> None:
    db: Session = session_factory()
    try:
        repository = ModuleRepository(db)
        module = repository.get_by_id(module_id)
        if module is None:
            raise ValueError("Módulo não encontrado.")
        if not module.is_available:
            raise ValueError("O módulo está indisponível e não pode ser configurado.")

        definitions = {
            definition.key: definition
            for definition in repository.list_variable_definitions(module_id)
            if definition.is_user_editable
        }
        unknown_keys = set(values).difference(definitions)
        if unknown_keys:
            raise ValueError("Foram informadas configurações que não pertencem ao módulo.")

        for key, definition in definitions.items():
            value = values.get(key, "")
            if not isinstance(value, str):
                raise ValueError(f"O campo '{definition.label}' deve receber texto.")
            if definition.is_required and not value.strip():
                raise ValueError(f"Preencha o campo obrigatório '{definition.label}'.")

            persisted_value = repository.get_variable_value(definition.id)
            if persisted_value is None:
                persisted_value = ModuleVariableValue(
                    variable_definition_id=definition.id,
                    value_text=value,
                )
                db.add(persisted_value)
            else:
                persisted_value.value_text = value
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_effective_module_variables(
    db: Session,
    module_id: int,
) -> dict[str, str]:
    repository = ModuleRepository(db)
    variables: dict[str, str] = {}
    for definition in repository.list_variable_definitions(module_id):
        if definition.is_user_editable:
            persisted_value = repository.get_variable_value(definition.id)
            value = (
                persisted_value.value_text
                if persisted_value is not None
                else definition.default_value or ""
            )
        else:
            value = definition.default_value or ""

        if definition.is_required and not value.strip():
            raise ValueError(
                f"Configure o campo obrigatório '{definition.label}' antes de executar o módulo."
            )
        variables[definition.key] = value
    return variables


def _read_module_readme(
    manifest_directory: str | None,
    readme_path: str | None,
) -> tuple[str, str]:
    if not manifest_directory or not readme_path:
        return "", ""

    module_folder = Path(manifest_directory).resolve()
    resolved_readme = Path(readme_path).resolve()
    try:
        resolved_readme.relative_to(module_folder)
    except ValueError:
        return "", "O caminho do README é inválido."
    if not resolved_readme.is_file():
        return "", "O README do módulo não foi encontrado."
    try:
        content = resolved_readme.read_text(encoding="utf-8")
        if re.search(r"<[A-Za-z/][^>]*>", content):
            return "", "O README contém HTML e não pode ser renderizado nesta versão."
        return content, ""
    except Exception:
        return "", "Não foi possível carregar o README do módulo."


def _read_module_manifest(
    manifest_directory: str | None,
) -> tuple[str, str]:
    if not manifest_directory:
        return "", ""

    module_folder = Path(manifest_directory).resolve()
    manifest_path = (module_folder / "module.json").resolve()
    try:
        manifest_path.relative_to(module_folder)
    except ValueError:
        return "", "O caminho do module.json é inválido."
    if not manifest_path.is_file():
        return "", "O arquivo module.json não foi encontrado."
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return json.dumps(data, ensure_ascii=False, indent=4), ""
    except json.JSONDecodeError:
        return "", "O arquivo module.json contém JSON inválido."
    except Exception:
        return "", "Não foi possível carregar o module.json."


def _detect_argument_capability(module) -> tuple[bool, str]:
    if (
        not module.is_available
        or not module.is_executable
        or module.request_method != "PYTHON"
        or not module.request_url
    ):
        return False, ""
    try:
        return (
            ModuleRunner().has_argument_search(
                module.request_url,
                module.module_public_key,
            ),
            "",
        )
    except Exception as error:
        message = str(error).strip() or "Falha ao inspecionar os argumentos do módulo."
        return False, message


def _build_technical_errors(
    repository: ModuleRepository,
    module,
    runtime_statuses: dict[int, str],
    invalid_modules,
) -> list[dict[str, object]]:
    affected_modules = [module, *repository.list_descendants(module.id)]
    affected_public_keys = {
        affected_module.module_public_key
        for affected_module in affected_modules
    }
    invalid_by_key = {
        item.module_public_key: item
        for item in invalid_modules
        if item.module_public_key
    }
    errors: list[dict[str, object]] = []
    for affected_module in affected_modules:
        runtime_status = runtime_statuses.get(affected_module.id)
        invalid_info = invalid_by_key.get(affected_module.module_public_key)
        message = affected_module.validation_error or ""
        if not message and invalid_info is not None:
            message = invalid_info.message
        if not message and runtime_status == "com erro":
            message = "O backend do módulo falhou durante a inicialização."
        if not message and not affected_module.is_available:
            message = "O módulo está indisponível."
        if not message:
            continue

        log_path = invalid_info.log_path if invalid_info is not None else ""
        if not log_path and affected_module.manifest_directory:
            candidate_path = Path(affected_module.manifest_directory) / "module.log"
            if candidate_path.is_file():
                log_path = str(candidate_path.resolve())
        errors.append(
            _build_technical_error(
                affected_module,
                message,
                log_path=log_path,
                is_submodule=affected_module.id != module.id,
            )
        )
    for invalid_info in invalid_modules:
        if (
            not invalid_info.parent_public_key
            or invalid_info.parent_public_key not in affected_public_keys
            or invalid_info.module_public_key in affected_public_keys
        ):
            continue
        errors.append(
            {
                "module_id": invalid_info.module_public_key,
                "module_name": invalid_info.folder_name,
                "message": invalid_info.message,
                "log_path": invalid_info.log_path,
                "is_submodule": True,
            }
        )
    return errors


def _build_technical_error(
    module,
    message: str,
    *,
    log_path: str = "",
    is_submodule: bool = False,
) -> dict[str, object]:
    return {
        "module_id": module.id,
        "module_name": module.name,
        "message": message,
        "log_path": log_path,
        "is_submodule": is_submodule,
    }


def _deduplicate_errors(
    errors: list[dict[str, object]],
) -> list[dict[str, object]]:
    unique: list[dict[str, object]] = []
    seen: set[tuple[object, object]] = set()
    for error in errors:
        key = (error.get("module_id"), error.get("message"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(error)
    return unique


def _build_model_data(module) -> list[tuple[str, str]]:
    return [
        ("ID", str(module.id)),
        ("Chave pública", module.module_public_key),
        ("Nome", module.name),
        ("Ícone", module.icon or "extension"),
        ("Nome de chamada original", module.call_name),
        ("Nome de chamada personalizado", module.custom_call_name or "-"),
        ("Descrição", module.description or "-"),
        ("Método de execução", module.request_method or "-"),
        ("Destino", module.request_url or "-"),
        ("Executável", _format_boolean(module.is_executable)),
        ("Disponível", _format_boolean(module.is_available)),
        ("Erro de validação", module.validation_error or "-"),
        ("Diretório do manifesto", module.manifest_directory or "-"),
        ("Caminho do README", module.readme_path or "-"),
        ("Runtime", module.runtime_type or "-"),
        ("Suporta iniciar com a IRIS", _format_boolean(module.supports_auto_start)),
        ("Iniciar com a IRIS", _format_boolean(module.auto_start_enabled)),
        ("ID do módulo pai", str(module.parent_module_id or "-")),
        ("Criado em", _format_datetime(module.created_date)),
        ("Editado em", _format_datetime(module.edited_date)),
    ]


def _format_boolean(value: object) -> str:
    return "Sim" if bool(value) else "Não"


def _format_datetime(value) -> str:
    if value is None:
        return "-"
    return value.strftime("%d/%m/%Y %H:%M:%S")


def _normalize_custom_call_name(custom_call_name: str | None) -> str:
    normalized_value = (custom_call_name or "").strip()
    if len(normalized_value) > 100:
        raise ValueError("O nome de chamada personalizado aceita até 100 caracteres.")
    if "/" in normalized_value:
        raise ValueError("O nome de chamada personalizado não pode conter '/'.")
    return normalized_value


def _module_status(
    is_available: bool,
    validation_error: str | None,
    runtime_status: str | None,
) -> str:
    if runtime_status == "com erro":
        return runtime_status
    if not is_available:
        return "inválido" if validation_error else "indisponível"
    return runtime_status or "disponível"


def module_has_problem(module) -> bool:
    validation_error = _get_module_value(module, "validation_error", "")
    is_available = _get_module_value(module, "is_available")
    status = str(
        _get_module_value(module, "runtime_status", "")
        or _get_module_value(module, "status", "")
        or ""
    ).strip().casefold()
    return (
        bool(validation_error)
        or is_available is False
        or status in {"com erro", "erro", "error"}
    )


def _get_module_value(module, key: str, default=None):
    if isinstance(module, Mapping):
        return module.get(key, default)
    return getattr(module, key, default)
