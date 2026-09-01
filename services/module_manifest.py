from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlsplit


SCHEMA_VERSION = 1
PUBLIC_KEY_PATTERN = re.compile(r"^[a-z0-9._-]+$")
VARIABLE_KEY_PATTERN = re.compile(r"^[a-z0-9._-]+$")
MATERIAL_ICON_PATTERN = re.compile(r"^[a-z0-9_]+$")
SUPPORTED_VARIABLE_TYPES = {"text"}
SUPPORTED_HTTP_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
}
SUPPORTED_HTTP_BODY_MODES = {
    "none",
    "raw_json",
    "raw_text",
    "form_urlencoded",
}
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
SENSITIVE_HTTP_NAME_PATTERN = re.compile(
    r"(?:^|[._\-\s])(?:api[._\-\s]*key|authorization|credential|credentials|"
    r"cookie|login|password|private|secret|senha|token)(?:$|[._\-\s])",
    re.IGNORECASE,
)
SENSITIVE_HTTP_VALUE_PATTERN = re.compile(
    r"(?:\b(?:basic|bearer)\s+\S+|\bsk-[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)


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
class ManifestHttpItem:
    key: str
    value: str
    description: str
    enabled: bool


@dataclass(frozen=True)
class ManifestHttpBody:
    mode: str
    content: str | tuple[ManifestHttpItem, ...]


@dataclass(frozen=True)
class ManifestHttpScripts:
    pre_request: str
    post_response: str


@dataclass(frozen=True)
class ManifestHttpRequest:
    method: str
    url: str
    argument_enabled: bool
    params: tuple[ManifestHttpItem, ...]
    authorization_type: str
    headers: tuple[ManifestHttpItem, ...]
    body: ManifestHttpBody
    scripts: ManifestHttpScripts


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
    http_request: ManifestHttpRequest | None
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
    http_request_data = data.get("http_request")
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
    http_request = _parse_http_request(http_request_data)
    if runtime_type is not None and http_request is not None:
        raise ManifestValidationError(
            "Um módulo não pode declarar runtime Python e http_request simultaneamente nesta versão."
        )
    is_executable = (
        explicit_executable
        if explicit_executable is not None
        else runtime_type is not None or http_request is not None
    )
    if http_request is not None and not is_executable:
        raise ManifestValidationError(
            "Um módulo com http_request não pode declarar module.is_executable como false."
        )
    if is_executable and entrypoint_path is None and http_request is None:
        raise ManifestValidationError(
            "Um módulo executável precisa declarar um runtime com entry point ou http_request."
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
        http_request=http_request,
        variables=variables,
    )


def _parse_http_request(http_request_data: object) -> ManifestHttpRequest | None:
    if http_request_data is None:
        return None
    if not isinstance(http_request_data, dict):
        raise ManifestValidationError(
            "O campo 'http_request' deve ser um objeto JSON ou null."
        )
    _ensure_exact_fields(
        http_request_data,
        {
            "method",
            "url",
            "argument_enabled",
            "params",
            "authorization",
            "headers",
            "body",
            "scripts",
        },
        "http_request",
    )

    method = _required_string(http_request_data, "method").upper()
    if method not in SUPPORTED_HTTP_METHODS:
        raise ManifestValidationError(
            f"O método HTTP '{method}' não é suportado nesta versão."
        )

    url = _required_string(http_request_data, "url")
    if not url.startswith(("http://", "https://")):
        raise ManifestValidationError(
            "A URL HTTP deve começar com http:// ou https://."
        )

    argument_enabled = _required_boolean(http_request_data, "argument_enabled")
    params = _parse_http_items(
        _required_field(http_request_data, "params"),
        "params",
    )
    authorization_type = _parse_http_authorization(
        _required_field(http_request_data, "authorization")
    )
    headers = _parse_http_items(
        _required_field(http_request_data, "headers"),
        "headers",
    )
    body = _parse_http_body(_required_field(http_request_data, "body"))
    scripts = _parse_http_scripts(_required_field(http_request_data, "scripts"))
    _validate_http_safety(url, params, headers, body)

    return ManifestHttpRequest(
        method=method,
        url=url,
        argument_enabled=argument_enabled,
        params=params,
        authorization_type=authorization_type,
        headers=headers,
        body=body,
        scripts=scripts,
    )


def _parse_http_items(
    items_data: object,
    field_name: str,
) -> tuple[ManifestHttpItem, ...]:
    if not isinstance(items_data, list):
        raise ManifestValidationError(
            f"O campo 'http_request.{field_name}' deve ser uma lista."
        )

    items: list[ManifestHttpItem] = []
    for item_data in items_data:
        if not isinstance(item_data, dict):
            raise ManifestValidationError(
                f"Cada item de 'http_request.{field_name}' deve ser um objeto JSON."
            )
        _ensure_exact_fields(
            item_data,
            {"key", "value", "description", "enabled"},
            f"http_request.{field_name}",
        )
        items.append(
            ManifestHttpItem(
                key=_required_text(item_data, "key"),
                value=_required_text(item_data, "value"),
                description=_required_text(item_data, "description"),
                enabled=_required_boolean(item_data, "enabled"),
            )
        )
    return tuple(items)


def _parse_http_authorization(authorization_data: object) -> str:
    if not isinstance(authorization_data, dict):
        raise ManifestValidationError(
            "O campo 'http_request.authorization' deve ser um objeto JSON."
        )
    if set(authorization_data) != {"type"}:
        raise ManifestValidationError(
            "Authorization aceita somente {'type': 'none'} nesta versão; credenciais não são suportadas."
        )
    authorization_type = _required_string(authorization_data, "type")
    if authorization_type != "none":
        raise ManifestValidationError(
            "Authorization com token, senha, API key ou credencial não é suportada nesta versão."
        )
    return authorization_type


def _parse_http_body(body_data: object) -> ManifestHttpBody:
    if not isinstance(body_data, dict):
        raise ManifestValidationError(
            "O campo 'http_request.body' deve ser um objeto JSON."
        )
    _ensure_exact_fields(
        body_data,
        {"mode", "content"},
        "http_request.body",
    )
    mode = _required_string(body_data, "mode")
    if mode not in SUPPORTED_HTTP_BODY_MODES:
        raise ManifestValidationError(
            f"O modo de body HTTP '{mode}' não é suportado nesta versão."
        )

    content_data = _required_field(body_data, "content")
    if mode == "form_urlencoded":
        content: str | tuple[ManifestHttpItem, ...] = _parse_http_items(
            content_data,
            "body.content",
        )
    else:
        if not isinstance(content_data, str):
            raise ManifestValidationError(
                f"O conteúdo do body no modo '{mode}' deve ser texto."
            )
        content = content_data
    return ManifestHttpBody(mode=mode, content=content)


def _parse_http_scripts(scripts_data: object) -> ManifestHttpScripts:
    if not isinstance(scripts_data, dict):
        raise ManifestValidationError(
            "O campo 'http_request.scripts' deve ser um objeto JSON."
        )
    _ensure_exact_fields(
        scripts_data,
        {"pre_request", "post_response"},
        "http_request.scripts",
    )
    pre_request = _required_text(scripts_data, "pre_request")
    post_response = _required_text(scripts_data, "post_response")
    if pre_request.strip() or post_response.strip():
        raise ManifestValidationError(
            "Scripts HTTP ainda não são suportados e não serão executados nesta versão."
        )
    return ManifestHttpScripts(
        pre_request=pre_request,
        post_response=post_response,
    )


def _validate_http_safety(
    url: str,
    params: tuple[ManifestHttpItem, ...],
    headers: tuple[ManifestHttpItem, ...],
    body: ManifestHttpBody,
) -> None:
    parsed_url = urlsplit(url)
    if (
        parsed_url.username is not None
        or parsed_url.password is not None
        or SENSITIVE_HTTP_VALUE_PATTERN.search(url)
    ):
        raise ManifestValidationError(
            "O manifesto HTTP não pode conter token, senha, API key ou credencial."
        )
    for query_key, query_value in parse_qsl(parsed_url.query, keep_blank_values=True):
        _reject_sensitive_http_item(query_key, query_value)
    for item in (*params, *headers):
        _reject_sensitive_http_item(item.key, item.value)

    if isinstance(body.content, tuple):
        for item in body.content:
            _reject_sensitive_http_item(item.key, item.value)
    else:
        _reject_sensitive_http_content(body.content)


def _reject_sensitive_http_item(key: str, value: str) -> None:
    if SENSITIVE_HTTP_NAME_PATTERN.search(key) or SENSITIVE_HTTP_VALUE_PATTERN.search(value):
        raise ManifestValidationError(
            "O manifesto HTTP não pode conter token, senha, API key ou credencial."
        )


def _reject_sensitive_http_content(content: str) -> None:
    if SENSITIVE_HTTP_VALUE_PATTERN.search(content):
        raise ManifestValidationError(
            "O manifesto HTTP não pode conter token, senha, API key ou credencial."
        )
    if re.search(
        r"[\"']?(?:api[._\- ]*key|authorization|credential|password|secret|senha|token)"
        r"[\"']?\s*[:=]",
        content,
        re.IGNORECASE,
    ):
        raise ManifestValidationError(
            "O manifesto HTTP não pode conter token, senha, API key ou credencial."
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


def _ensure_exact_fields(
    data: dict,
    expected_fields: set[str],
    label: str,
) -> None:
    if set(data) != expected_fields:
        raise ManifestValidationError(
            f"O campo '{label}' deve conter somente: "
            f"{', '.join(sorted(expected_fields))}."
        )


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


def _required_text(data: dict, key: str) -> str:
    value = _required_field(data, key)
    if not isinstance(value, str):
        raise ManifestValidationError(f"O campo '{key}' deve ser texto.")
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
