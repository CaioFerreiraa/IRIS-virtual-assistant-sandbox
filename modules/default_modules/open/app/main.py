import os
import platform
import subprocess
from pathlib import Path


MAX_RESULTS = 12


def _desktop_candidates() -> list[Path]:
    candidates: list[Path] = []

    for environment_variable in (
        "OneDrive",
        "OneDriveConsumer",
        "OneDriveCommercial",
    ):
        base_path = os.environ.get(environment_variable)

        if base_path:
            candidates.append(Path(base_path) / "Desktop")

    user_profile = os.environ.get("USERPROFILE")

    if user_profile:
        candidates.append(Path(user_profile) / "Desktop")

    candidates.append(Path.home() / "Desktop")

    unique_candidates: list[Path] = []

    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)

    return unique_candidates


def _desktop_path() -> Path:
    for candidate in _desktop_candidates():
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()

    raise FileNotFoundError(
        "Não foi possível localizar a pasta da Área de Trabalho."
    )


def _matches_query(path: Path, query: str) -> bool:
    normalized_query = query.strip().casefold()

    if not normalized_query:
        return True

    return normalized_query in path.name.casefold()


def _item_description(item: Path) -> str:
    if item.is_dir():
        return "Pasta"

    if item.suffix.casefold() == ".lnk":
        return "Atalho"

    return "Arquivo"


def search_arguments(query: str = "") -> list[dict[str, str]]:
    desktop_path = _desktop_path()

    items = [
        item
        for item in desktop_path.iterdir()
        if not item.name.startswith(".")
        and _matches_query(item, query)
    ]

    items.sort(
        key=lambda item: (
            not item.is_dir(),
            item.name.casefold(),
        )
    )

    return [
        {
            "label": item.name,
            "value": str(item),
            "description": _item_description(item),
        }
        for item in items[:MAX_RESULTS]
    ]


def execute(argument: str | None = None) -> dict[str, str | bool]:
    if not argument:
        raise ValueError(
            "Informe o item da Área de Trabalho que deseja abrir."
        )

    desktop_path = _desktop_path()
    target = Path(argument).expanduser().resolve()

    try:
        target.relative_to(desktop_path)
    except ValueError as error:
        raise ValueError(
            "O item informado não pertence à Área de Trabalho."
        ) from error

    if not target.exists():
        raise FileNotFoundError(
            f"Item não encontrado: {target}"
        )

    system = platform.system().casefold()

    if system == "windows":
        os.startfile(str(target))  # type: ignore[attr-defined]
    elif system == "darwin":
        subprocess.run(
            ["open", str(target)],
            check=True,
        )
    else:
        subprocess.run(
            ["xdg-open", str(target)],
            check=True,
        )

    return {
        "success": True,
        "opened": str(target),
    }