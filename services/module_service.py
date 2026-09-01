from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
import re

from sqlalchemy.orm import Session

from database.db import SessionLocal
from database.models import Module, ModuleVariableValue
from repositories.module_repository import ModuleRepository
from services.http_service import ModuleHttpRequestService, build_http_request_detail
from services.module_registry_state import get_module_registry_state
from core.module_runner import ModuleRunner


DEFAULT_MODULES_ROOT = Path(__file__).resolve().parent.parent / "modules" / "default_modules"


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
        http_request, http_request_error = _build_http_request_detail(module)
        if http_request_error:
            technical_errors.append(
                _build_technical_error(module, http_request_error)
            )
        has_arguments, argument_error = _detect_argument_capability(module)
        if argument_error:
            technical_errors.append(
                _build_technical_error(module, argument_error)
            )
        effective_validation_error = module.validation_error or http_request_error
        effective_is_available = bool(
            module.is_available and not http_request_error
        )
        status = _module_status(
            effective_is_available,
            effective_validation_error,
            runtime_status,
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
            "is_available": effective_is_available,
            "validation_error": effective_validation_error or "",
            "status": status,
            "supports_auto_start": bool(module.supports_auto_start),
            "auto_start_enabled": bool(module.auto_start_enabled),
            "is_root_module": module.parent_module_id is None,
            "can_auto_start": bool(
                effective_is_available
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
            "http_request": http_request,
            "technical_errors": _deduplicate_errors(technical_errors),
            "model_data": _build_model_data(module),
            "variables": variables,
        }
    finally:
        db.close()


def _build_http_request_detail(module) -> tuple[dict[str, object] | None, str]:
    if module.http_request is None:
        return None, ""
    try:
        return build_http_request_detail(module.http_request), ""
    except Exception as error:
        message = str(error).strip() or "A configuração HTTP do módulo é inválida."
        return None, message


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


def save_http_request_argument(
    module_id: int,
    argument: str,
    session_factory=SessionLocal,
) -> None:
    ModuleHttpRequestService(session_factory).save_argument(
        module_id,
        argument,
    )


def save_http_request_definition(
    module_id: int,
    values: Mapping[str, object],
    session_factory=SessionLocal,
) -> dict[str, object]:
    argument_enabled = values.get("argument_enabled")
    if type(argument_enabled) is not bool:
        raise ValueError("O estado do argumento da execução deve ser booleano.")
    return ModuleHttpRequestService(session_factory).save_definition(
        module_id,
        method=str(values.get("method", "")),
        url=str(values.get("url", "")),
        argument_enabled=argument_enabled,
        argument=str(values.get("argument", "")),
        params_json=str(values.get("params_json", "")),
        authorization_json=str(values.get("authorization_json", "")),
        headers_json=str(values.get("headers_json", "")),
        body_json=str(values.get("body_json", "")),
        scripts_json=str(values.get("scripts_json", "")),
    )


def reset_http_request_definition(
    module_id: int,
    session_factory=SessionLocal,
) -> dict[str, object]:
    return ModuleHttpRequestService(session_factory).reset_definition_from_manifest(
        module_id
    )


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
    if not readme_path:
        return "", ""

    resolved_readme = Path(readme_path).resolve()
    module_folder = (
        Path(manifest_directory).resolve()
        if manifest_directory
        else DEFAULT_MODULES_ROOT.resolve()
    )
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


MODEL_FIELD_PRESENTATION = {
    "id": ("ID", "Identificador numérico interno do módulo no banco de dados."),
    "module_public_key": ("Chave pública", "Chave pública única e estável usada para identificar o módulo."),
    "name": ("Nome", "Nome do módulo apresentado na interface."),
    "call_name": ("Nome de chamada original", "Nome definido pelo desenvolvedor para localizar e chamar o módulo."),
    "custom_call_name": ("Nome de chamada personalizado", "Nome de chamada alternativo escolhido pelo usuário."),
    "description": ("Descrição", "Resumo da capacidade oferecida pelo módulo."),
    "icon": ("Ícone", "Nome do ícone Material Symbols usado para representar o módulo."),
    "request_method": ("Método de execução", "Tipo de execução configurado para o módulo, como PYTHON ou GET legado."),
    "request_url": ("Destino", "Caminho do entry point ou endereço usado durante a execução."),
    "is_executable": ("Executável", "Indica se o módulo pode disparar uma ação."),
    "is_available": ("Disponível", "Indica se o módulo passou pela validação e está disponível para uso."),
    "validation_error": ("Erro de validação", "Motivo técnico que tornou o módulo inválido ou indisponível."),
    "manifest_directory": ("Diretório do manifesto", "Pasta do módulo que contém o arquivo module.json."),
    "readme_path": ("Caminho do README", "Caminho do arquivo de documentação do módulo."),
    "runtime_type": ("Runtime", "Ambiente configurado para executar o módulo."),
    "supports_auto_start": ("Suporta iniciar com a IRIS", "Indica se o runtime declara suporte à inicialização automática."),
    "auto_start_enabled": ("Iniciar com a IRIS", "Preferência que inicia o módulo junto com a IRIS quando houver suporte."),
    "parent_module_id": ("ID do módulo pai", "Identificador do módulo pai; vazio quando este é um módulo raiz."),
    "created_date": ("Criado em", "Data e hora em que o registro do módulo foi criado."),
    "edited_date": ("Editado em", "Data e hora da última alteração persistida no registro do módulo."),
}


def _build_model_data(module: Module) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    for column in Module.__table__.columns:
        field_name = column.key
        label, help_text = MODEL_FIELD_PRESENTATION.get(
            field_name,
            (
                field_name.replace("_", " ").capitalize(),
                f"Valor persistido na coluna '{field_name}' do módulo.",
            ),
        )
        fields.append(
            {
                "name": field_name,
                "label": label,
                "value": _format_model_value(getattr(module, field_name)),
                "help": help_text,
            }
        )
    return fields


def _format_model_value(value: object) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return _format_boolean(value)
    if isinstance(value, datetime):
        return _format_datetime(value)
    return str(value)


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
    return runtime_status or "offline"


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
