def text_or_empty(value: str | None) -> str:
    return value.strip() if value else ""