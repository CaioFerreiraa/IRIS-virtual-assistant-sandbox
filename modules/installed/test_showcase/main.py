from __future__ import annotations


_is_started = False


def execute(
    argument: str | None = None,
    variables: dict[str, str] | None = None,
) -> dict[str, str | bool]:
    settings = variables or {}
    editable_text = settings.get("editable_text", "") or "sem texto editável"
    required_text = settings.get("required_text", "")
    internal_text = settings.get("internal_text", "")
    received_argument = (argument or "sem argumento").strip()
    return {
        "success": True,
        "message": (
            "Catálogo executado com sucesso. "
            f"Argumento: {received_argument}; "
            f"editável: {editable_text}; "
            f"obrigatório: {required_text}; "
            f"interno: {internal_text}."
        ),
    }


def start(variables: dict[str, str] | None = None) -> None:
    del variables
    global _is_started
    _is_started = True


def stop() -> None:
    global _is_started
    _is_started = False
