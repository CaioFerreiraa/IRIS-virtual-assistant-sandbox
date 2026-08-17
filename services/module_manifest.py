from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


SCHEMA_VERSION = 1
PUBLIC_KEY_PATTERN = re.compile(r"^[a-z0-9._-]+$")
VARIABLE_KEY_PATTERN = re.compile(r"^[a-z0-9._-]+$")
MATERIAL_ICON_PATTERN = re.compile(r"^[a-z0-9_]+$")
SUPPORTED_VARIABLE_TYPES = {"text"}
SENSITIVE_VARIABLE_WORDS = {
    "credential",
    "credentials",
    "login",
    "password",
    "private",
    "secret",
    "senha",
    "token",
}
SECRET_DECLARATION_FIELDS = {
    "encrypted",
    "is_encrypted",
    "is_private",
    "is_secret",
    "private",
    "secret",
    "sensitive",
}


class ManifestValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ManifestVariable:
    key: str
    label: str
    description: str
    type: str
    required: bool
    user_editable: bool
    default_value: str | None
    display_order: int


@dataclass(frozen=True)
class ModuleManifest:
    folder: Path
    module_public_key: str
    name: str
    call_name: str
    icon: str
    parent_public_key: str | None
    description: str
    readme_path: Path
    runtime_type: str | None
    entrypoint_path: Path | None
    supports_auto_start: bool
    is_executable: bool
    variables: tuple[ManifestVariable, ...]


def parse_module_manifest(data: object, folder: Path) -> ModuleManifest:
    if not isinstance(data, dict):
        raise ManifestValidationError("O conteúdo do manifesto deve ser um objeto JSON.")

    schema_version = _required_field(data, "schema_version")
    if type(schema_version) is not int:
        raise ManifestValidationError("O campo 'schema_version' deve ser um número inteiro.")
    if schema_version != SCHEMA_VERSION:
        raise ManifestValidationError(
            f"A versão de schema {schema_version} não é compatível com esta versão da IRIS."
        )

    module_data = _required_mapping(data, "module")
    runtime_data = _required_field(data, "runtime")
    variables_data = _required_field(data, "variables")

    module_public_key = _required_string(module_data, "module_public_key")
    _validate_public_key(module_public_key, "module_public_key")
    name = _required_string(module_data, "name")
    call_name = _required_string(module_data, "call_name")
    icon = _optional_string(module_data, "icon", "extension")
    if not icon or len(icon) > 100 or not MATERIAL_ICON_PATTERN.fullmatch(icon):
        raise ManifestValidationError(
            "O campo 'module.icon' deve conter um nome válido do Material Icons."
        )
    parent_public_key = _nullable_string(module_data, "parent_public_key")
    if parent_public_key is not None:
        _validate_public_key(parent_public_key, "parent_public_key")
    if parent_public_key == module_public_key:
        raise ManifestValidationError("Um módulo não pode declarar a si mesmo como pai.")

    readme_value = _required_string(module_data, "readme")
    readme_path = _resolve_inside_folder(folder, readme_value, "README")
    if not readme_path.is_file():
        raise ManifestValidationError("O arquivo README declarado não foi encontrado.")

    description = _optional_string(module_data, "description", "")
    explicit_executable = module_data.get("is_executable")
    if explicit_executable is not None and type(explicit_executable) is not bool:
        raise ManifestValidationError("O campo 'module.is_executable' deve ser booleano.")

    runtime_type, entrypoint_path, supports_auto_start = _parse_runtime(
        runtime_data,
        folder,
    )
    is_executable = (
        explicit_executable
        if explicit_executable is not None
        else runtime_type is not None
    )
    if is_executable and entrypoint_path is None:
        raise ManifestValidationError(
            "Um módulo executável precisa declarar um runtime com entry point."
        )

    variables = _parse_variables(variables_data)
    return ModuleManifest(
        folder=folder.resolve(),
        module_public_key=module_public_key,
        name=name,
        call_name=call_name,
        icon=icon,
        parent_public_key=parent_public_key,
        description=description,
        readme_path=readme_path,
        runtime_type=runtime_type,
        entrypoint_path=entrypoint_path,
        supports_auto_start=supports_auto_start,
        is_executable=is_executable,
        variables=variables,
    )


def _parse_runtime(
    runtime_data: object,
    folder: Path,
) -> tuple[str | None, Path | None, bool]:
    if runtime_data is None:
        return None, None, False
    if not isinstance(runtime_data, dict):
        raise ManifestValidationError("O campo 'runtime' deve ser um objeto ou null.")

    runtime_type = _required_string(runtime_data, "type")
    if runtime_type != "python":
        raise ManifestValidationError(
            f"O runtime '{runtime_type}' não é suportado nesta versão."
        )
    entrypoint_value = _required_string(runtime_data, "entrypoint")
    entrypoint_path = _resolve_inside_folder(folder, entrypoint_value, "entry point")
    if not entrypoint_path.is_file():
        raise ManifestValidationError("O entry point declarado não foi encontrado.")

    supports_auto_start = _required_boolean(runtime_data, "supports_auto_start")
    return runtime_type, entrypoint_path, supports_auto_start


def _parse_variables(variables_data: object) -> tuple[ManifestVariable, ...]:
    if not isinstance(variables_data, list):
        raise ManifestValidationError("O campo 'variables' deve ser uma lista.")

    variables: list[ManifestVariable] = []
    seen_keys: set[str] = set()
    for display_order, variable_data in enumerate(variables_data):
        if not isinstance(variable_data, dict):
            raise ManifestValidationError("Cada variável deve ser um objeto JSON.")
        if SECRET_DECLARATION_FIELDS.intersection(variable_data):
            raise ManifestValidationError(
                "Variáveis secretas, privadas ou criptografadas não são compatíveis nesta versão."
            )

        key = _required_string(variable_data, "key")
        _validate_variable_key(key)
        if key in seen_keys:
            raise ManifestValidationError(f"A variável '{key}' foi declarada mais de uma vez.")
        seen_keys.add(key)

        label = _required_string(variable_data, "label")
        description = _required_string(variable_data, "description")
        variable_type = _required_string(variable_data, "type")
        if variable_type not in SUPPORTED_VARIABLE_TYPES:
            raise ManifestValidationError(
                f"O tipo de variável '{variable_type}' não é suportado nesta versão."
            )
        required = _required_boolean(variable_data, "required")
        user_editable = _required_boolean(variable_data, "user_editable")
        default_value = _required_field(variable_data, "default_value")
        if default_value is not None and not isinstance(default_value, str):
            raise ManifestValidationError(
                f"O valor padrão da variável '{key}' deve ser texto ou null."
            )
        if required and not user_editable and not (default_value or "").strip():
            raise ManifestValidationError(
                f"A variável obrigatória e não editável '{key}' precisa de um valor padrão."
            )

        variables.append(
            ManifestVariable(
                key=key,
                label=label,
                description=description,
                type=variable_type,
                required=required,
                user_editable=user_editable,
                default_value=default_value,
                display_order=display_order,
            )
        )
    return tuple(variables)


def _validate_public_key(value: str, field_name: str) -> None:
    if not PUBLIC_KEY_PATTERN.fullmatch(value):
        raise ManifestValidationError(
            f"O campo '{field_name}' aceita somente letras minúsculas, números, pontos, hífens e underscores."
        )


def _validate_variable_key(value: str) -> None:
    if not VARIABLE_KEY_PATTERN.fullmatch(value):
        raise ManifestValidationError(
            "A chave da variável aceita somente letras minúsculas, números, pontos, hífens e underscores."
        )
    key_words = {word for word in re.split(r"[._-]+", value) if word}
    if key_words.intersection(SENSITIVE_VARIABLE_WORDS):
        raise ManifestValidationError(
            f"A variável '{value}' parece armazenar dado sensível e não é compatível nesta versão."
        )


def _resolve_inside_folder(folder: Path, relative_value: str, label: str) -> Path:
    relative_path = Path(relative_value)
    if relative_path.is_absolute():
        raise ManifestValidationError(f"O caminho do {label} deve ser relativo à pasta do módulo.")
    folder_path = folder.resolve()
    resolved_path = (folder_path / relative_path).resolve()
    try:
        resolved_path.relative_to(folder_path)
    except ValueError as error:
        raise ManifestValidationError(
            f"O caminho do {label} não pode escapar da pasta do módulo."
        ) from error
    return resolved_path


def _required_mapping(data: dict, key: str) -> dict:
    value = _required_field(data, key)
    if not isinstance(value, dict):
        raise ManifestValidationError(f"O campo '{key}' deve ser um objeto JSON.")
    return value


def _required_field(data: dict, key: str):
    if key not in data:
        raise ManifestValidationError(f"O campo obrigatório '{key}' não foi informado.")
    return data[key]


def _required_string(data: dict, key: str) -> str:
    value = _required_field(data, key)
    if not isinstance(value, str):
        raise ManifestValidationError(f"O campo '{key}' deve ser texto.")
    value = value.strip()
    if not value:
        raise ManifestValidationError(f"O campo obrigatório '{key}' não pode ficar vazio.")
    return value


def _optional_string(data: dict, key: str, default: str) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ManifestValidationError(f"O campo '{key}' deve ser texto.")
    return value.strip()


def _nullable_string(data: dict, key: str) -> str | None:
    value = _required_field(data, key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ManifestValidationError(f"O campo '{key}' deve ser texto ou null.")
    value = value.strip()
    if not value:
        raise ManifestValidationError(f"O campo '{key}' não pode ser uma string vazia.")
    return value


def _required_boolean(data: dict, key: str) -> bool:
    value = _required_field(data, key)
    if type(value) is not bool:
        raise ManifestValidationError(f"O campo '{key}' deve ser booleano.")
    return value
