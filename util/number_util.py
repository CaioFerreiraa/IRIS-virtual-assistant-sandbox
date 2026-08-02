def int_or_none(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None