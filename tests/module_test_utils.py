from __future__ import annotations

import json
from pathlib import Path


VALID_ENTRYPOINT = """\
def execute(argument=None, variables=None):
    return {"success": True, "message": argument or "ok"}
"""


def build_manifest(
    public_key: str = "weather",
    *,
    parent_public_key: str | None = None,
    variables: list[dict] | None = None,
    runtime: dict | None | object = ...,
    is_executable: bool | None = None,
) -> dict:
    if runtime is ...:
        runtime = {
            "type": "python",
            "entrypoint": "main.py",
            "supports_auto_start": False,
        }
    module = {
        "module_public_key": public_key,
        "name": public_key.replace(".", " ").title(),
        "call_name": public_key.rsplit(".", 1)[-1],
        "parent_public_key": parent_public_key,
        "description": "Módulo temporário de teste.",
        "readme": "README.md",
    }
    if is_executable is not None:
        module["is_executable"] = is_executable
    return {
        "schema_version": 1,
        "module": module,
        "runtime": runtime,
        "variables": variables or [],
    }


def create_module_folder(
    installed_root: Path,
    folder_name: str,
    manifest: dict,
    *,
    main_source: str = VALID_ENTRYPOINT,
    create_readme: bool = True,
    create_entrypoint: bool = True,
) -> Path:
    folder = installed_root / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "module.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )
    if create_readme:
        (folder / "README.md").write_text("# Módulo de teste\n", encoding="utf-8")
    if create_entrypoint:
        (folder / "main.py").write_text(main_source, encoding="utf-8")
    return folder
