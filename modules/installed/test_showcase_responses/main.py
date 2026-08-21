from __future__ import annotations


_OPTIONS = (
    {
        "label": "Mensagem",
        "value": "message",
        "description": "Dicionário com success e message",
    },
    {
        "label": "Resultado",
        "value": "result",
        "description": "Dicionário com success e result",
    },
    {
        "label": "Recurso aberto",
        "value": "opened",
        "description": "Dicionário com success e opened",
    },
    {
        "label": "Retorno simples",
        "value": "plain",
        "description": "String normalizada automaticamente para result",
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


def execute(argument: str | None = None) -> dict[str, str | bool] | str:
    response_type = (argument or "").strip()
    if response_type == "message":
        return {"success": True, "message": "Resposta entregue pela chave message."}
    if response_type == "result":
        return {"success": True, "result": "Resposta entregue pela chave result."}
    if response_type == "opened":
        return {"success": True, "opened": "recurso-de-demonstracao"}
    if response_type == "plain":
        return "String convertida pelo runner para a chave result."
    raise ValueError("Escolha um tipo de resposta válido.")
