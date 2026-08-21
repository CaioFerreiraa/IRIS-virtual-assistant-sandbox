from __future__ import annotations


def run(argument: str | None = None) -> dict[str, str | bool]:
    value = (argument or "nenhum").strip()
    return {
        "success": True,
        "message": f"A função run foi chamada. Argumento: {value}.",
    }
