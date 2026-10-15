import json
from urllib.parse import quote, quote_plus


def redact_vault_values(value: object, vault: dict[str, str], *, preserve_result_fields: bool = False) -> object:
    """Oculta valores entregues nesta execução antes de retornar ou registrar."""
    if not vault:
        return value
    if isinstance(value, bytes):
        return redact_vault_values(value.decode("utf-8", errors="replace"), vault)
    if isinstance(value, str):
        variants = set()
        for secret in vault.values():
            if secret:
                variants.update((secret, quote(secret, safe=""), quote_plus(secret),
                                 json.dumps(secret, ensure_ascii=True)[1:-1]))
        for secret in sorted(variants, key=len, reverse=True):
            value = value.replace(secret, "[valor protegido]")
        return value
    if isinstance(value, dict):
        result_fields = {"success", "message", "result", "opened", "status_code", "reason_phrase", "elapsed_ms", "headers", "body"}
        return {(key if preserve_result_fields and key in result_fields else redact_vault_values(key, vault)): redact_vault_values(item, vault)
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_vault_values(item, vault) for item in value]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if str(value) in vault.values():
            return "[valor protegido]"
    return value
