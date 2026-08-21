from __future__ import annotations


def searchArguments() -> list[str]:
    return ["compatível um", "compatível dois", "compatível três"]


def execute(value: str) -> dict[str, str | bool]:
    return {
        "success": True,
        "message": f"Argumento posicional compatível recebido: {value}.",
    }
