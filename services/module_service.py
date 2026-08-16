from __future__ import annotations

from pathlib import Path
import re

from sqlalchemy.orm import Session

from database.db import SessionLocal
from database.models import ModuleVariableValue
from repositories.module_repository import ModuleRepository
from services.module_registry_state import get_module_registry_state


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

        runtime_status = get_module_registry_state().runtime_statuses.get(module.id)
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
        return {
            "id": module.id,
            "module_public_key": module.module_public_key,
            "name": module.name,
            "call_name": module.call_name,
            "custom_call_name": module.custom_call_name or "",
            "description": module.description or "",
            "is_available": bool(module.is_available),
            "validation_error": module.validation_error or "",
            "status": status,
            "supports_auto_start": bool(module.supports_auto_start),
            "auto_start_enabled": bool(module.auto_start_enabled),
            "can_auto_start": bool(
                module.is_available
                and module.runtime_type
                and module.supports_auto_start
                and module.parent_module_id is None
            ),
            "breadcrumb": repository.get_breadcrumb(module),
            "readme_content": readme_content,
            "readme_error": readme_error,
            "variables": variables,
        }
    finally:
        db.close()


def save_custom_call_name(
    module_id: int,
    custom_call_name: str | None,
    session_factory=SessionLocal,
) -> None:
    normalized_value = (custom_call_name or "").strip()
    if len(normalized_value) > 100:
        raise ValueError("O nome de chamada personalizado aceita até 100 caracteres.")
    if "/" in normalized_value:
        raise ValueError("O nome de chamada personalizado não pode conter '/'.")

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
            and module.runtime_type
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
        return "", "Este módulo não possui README gerenciado pelo registry."

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
