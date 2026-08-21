from __future__ import annotations


def execute(argument: str | None = None) -> dict[str, str | bool]:
    value = (argument or "nenhum").strip()
    return {
        "success": True,
        "message": f"A função execute foi chamada. Argumento: {value}.",
    }
