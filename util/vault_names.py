import json
import re


VAULT_NAME_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")
PLACEHOLDER_PATTERN = re.compile(r"\{\{([^{}]*)\}\}")
VAULT_PLACEHOLDER_PATTERN = re.compile(r"\{\{vk\.([A-Z_][A-Z0-9_]*)\}\}")
ACTIVE_VAULT_QUERY_PATTERN = re.compile(r"(?:\{\{)?vk\.([A-Za-z0-9_]*)$")


def normalize_vault_name(name: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name.strip()):
        raise ValueError("O nome da Vault Key deve começar com letra ou underscore e conter somente letras, números e underscores.")
    return name.strip().upper()


def validate_vault_names(names: object) -> tuple[str, ...]:
    if not isinstance(names, list) or any(
        not isinstance(name, str) or not VAULT_NAME_PATTERN.fullmatch(name)
        for name in names
    ):
        raise ValueError("vault_keys deve ser uma lista de nomes no padrão [A-Z_][A-Z0-9_]*.")
    if len(names) != len(set(names)):
        raise ValueError("vault_keys não pode conter nomes duplicados.")
    return tuple(names)


def load_vault_names(raw_value: str | None) -> tuple[str, ...]:
    try:
        return validate_vault_names(json.loads(raw_value or "[]"))
    except (TypeError, ValueError):
        raise ValueError("A declaração de Vault Keys do módulo é inválida. Ressincronize o módulo.") from None


def http_url_for_validation(url: str) -> str:
    """Permite validar a estrutura da URL sem acessar o Vault."""
    def replace(match: re.Match) -> str:
        placeholder = match.group(1)
        name = placeholder[3:] if placeholder.startswith("vk.") else ""
        if match.start() == 0 and VAULT_NAME_PATTERN.fullmatch(name):
            return "https://vault.invalid"
        return "vault-placeholder"
    return PLACEHOLDER_PATTERN.sub(replace, url)


def vault_placeholder(name: str) -> str:
    return f"{{{{vk.{name}}}}}"


def active_vault_query(value: str, cursor_offset: int | None = None) -> str | None:
    text = str(value or "")
    offset = len(text) if cursor_offset is None else max(0, min(cursor_offset, len(text)))
    match = ACTIVE_VAULT_QUERY_PATTERN.search(text[:offset])
    return match.group(1).upper() if match is not None else None


def insert_vault_placeholder(value: str, name: str,
                             cursor_offset: int | None = None) -> tuple[str, int]:
    text = str(value or "")
    offset = len(text) if cursor_offset is None else max(0, min(cursor_offset, len(text)))
    match = ACTIVE_VAULT_QUERY_PATTERN.search(text[:offset])
    placeholder = vault_placeholder(name)
    if match is None:
        inserted = text[:offset] + placeholder + text[offset:]
        return inserted, offset + len(placeholder)
    inserted = text[:match.start()] + placeholder + text[offset:]
    return inserted, match.start() + len(placeholder)


def invalid_vault_references(value: str, available_names: object) -> tuple[str, ...]:
    available = {str(name) for name in available_names}
    invalid: list[str] = []
    for match in PLACEHOLDER_PATTERN.finditer(str(value or "")):
        placeholder = match.group(1)
        if placeholder == "argument":
            continue
        if not placeholder.startswith("vk."):
            invalid.append(placeholder)
            continue
        name = placeholder[3:]
        if not VAULT_NAME_PATTERN.fullmatch(name) or name not in available:
            invalid.append(placeholder)
    return tuple(invalid)
