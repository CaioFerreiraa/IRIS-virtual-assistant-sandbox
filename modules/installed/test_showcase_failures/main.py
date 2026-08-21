from __future__ import annotations


def search_arguments(query: str = "") -> list[dict[str, str]]:
    options = (
        {
            "label": "Falha controlada",
            "value": "controlled",
            "description": "Retorna success false sem lançar exceção",
        },
        {
            "label": "Exceção",
            "value": "exception",
            "description": "Lança RuntimeError para testar o limite de execução",
        },
    )
    normalized_query = query.strip().casefold()
    return [
        option
        for option in options
        if not normalized_query
        or normalized_query in option["label"].casefold()
        or normalized_query in option["value"].casefold()
    ]


def execute(argument: str | None = None) -> dict[str, str | bool]:
    failure_type = (argument or "").strip()
    if failure_type == "controlled":
        return {
            "success": False,
            "message": "Falha controlada retornada pelo módulo de teste.",
        }
    if failure_type == "exception":
        raise RuntimeError("Exceção intencional do módulo de teste.")
    raise ValueError("Escolha um tipo de falha válido.")
