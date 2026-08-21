from __future__ import annotations


def main(argument: str | None = None) -> dict[str, str | bool]:
    value = (argument or "nenhum").strip()
    return {
        "success": True,
        "message": f"A função main foi chamada. Argumento: {value}.",
    }
