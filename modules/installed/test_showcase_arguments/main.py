from __future__ import annotations


_OPTIONS = (
    {
        "label": "Primeira opção",
        "value": "alpha",
        "description": "Valor técnico: alpha",
    },
    {
        "label": "Segunda opção",
        "value": "beta",
        "description": "Valor técnico: beta",
    },
    {
        "label": "Opção com acento",
        "value": "ação",
        "description": "Confirma texto UTF-8 em português do Brasil",
    },
)


def search_arguments(query: str = "") -> list[dict[str, str]]:
    normalized_query = query.strip().casefold()
    return [
        option
        for option in _OPTIONS
        if not normalized_query
        or normalized_query in option["label"].casefold()
        or normalized_query in option["value"].casefold()
    ]


def execute(argument: str | None = None) -> dict[str, str | bool]:
    value = (argument or "").strip()
    valid_values = {option["value"] for option in _OPTIONS}
    if not value:
        raise ValueError("Escolha ou digite um argumento para continuar.")
    if value not in valid_values:
        raise ValueError(f"O argumento '{value}' não pertence ao catálogo de teste.")
    return {
        "success": True,
        "message": f"Argumento recebido e validado: {value}.",
    }
