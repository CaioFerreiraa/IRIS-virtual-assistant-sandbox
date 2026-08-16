def execute(
    argument: str | None = None,
    variables: dict[str, str] | None = None,
) -> dict[str, str | bool]:
    prefix = (variables or {}).get("prefix", "IRIS")
    value = (argument or "módulo executado").strip()
    return {
        "success": True,
        "message": f"{prefix}: {value}",
    }
