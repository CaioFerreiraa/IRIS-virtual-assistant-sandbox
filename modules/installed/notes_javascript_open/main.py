from __future__ import annotations

import json
import os
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser


DEFAULT_PORT = 8765
OFFLINE_MESSAGE = (
    "O serviço de notas não está ativo. Habilite 'Iniciar com a IRIS' "
    "no módulo Notas e reinicie a aplicação."
)


def execute() -> dict[str, object]:
    port = _configured_port()
    base_url = f"http://127.0.0.1:{port}/"
    try:
        with urlopen(f"{base_url}health", timeout=1) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if response.status != 200 or payload.get("success") is not True:
                return {"success": False, "message": OFFLINE_MESSAGE}
    except (OSError, URLError, json.JSONDecodeError):
        return {"success": False, "message": OFFLINE_MESSAGE}

    try:
        opened = webbrowser.open(base_url)
    except Exception:
        opened = False
    if not opened:
        return {
            "success": False,
            "message": "Não foi possível abrir a interface de notas no navegador.",
        }
    return {
        "success": True,
        "message": "Notas abertas no navegador.",
        "opened": base_url,
    }


def _configured_port() -> int:
    raw_port = os.environ.get("IRIS_NOTES_PORT", str(DEFAULT_PORT))
    try:
        port = int(raw_port)
    except ValueError:
        return DEFAULT_PORT
    return port if 1 <= port <= 65535 else DEFAULT_PORT
