from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import urlopen


DEFAULT_PORT = 8765
HEALTH_TIMEOUT_SECONDS = 5.0
HEALTH_RETRY_SECONDS = 0.1
MODULE_DIRECTORY = Path(__file__).resolve().parent
SERVER_PATH = MODULE_DIRECTORY / "server.js"
NODE_LOG_PATH = MODULE_DIRECTORY / "node.log"


def start() -> subprocess.Popen:
    node_path = shutil.which("node")
    if node_path is None:
        raise RuntimeError(
            "Node.js não foi encontrado. Instale o Node.js para utilizar o módulo Notas."
        )

    port = _configured_port()
    _ensure_port_available(port)
    environment = os.environ.copy()
    environment["IRIS_NOTES_PORT"] = str(port)

    try:
        with NODE_LOG_PATH.open("ab") as log_file:
            process = subprocess.Popen(
                [node_path, str(SERVER_PATH)],
                cwd=str(MODULE_DIRECTORY),
                env=environment,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                shell=False,
            )
    except OSError as error:
        raise RuntimeError(
            "Não foi possível iniciar o processo Node.js do módulo Notas."
        ) from error

    try:
        _wait_for_health(process, port)
    except Exception:
        _terminate_process(process)
        raise
    return process


def _configured_port() -> int:
    raw_port = os.environ.get("IRIS_NOTES_PORT", str(DEFAULT_PORT))
    try:
        port = int(raw_port)
    except ValueError as error:
        raise RuntimeError("A porta configurada para o módulo Notas é inválida.") from error
    if not 1 <= port <= 65535:
        raise RuntimeError("A porta configurada para o módulo Notas é inválida.")
    return port


def _ensure_port_available(port: int) -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
    except OSError as error:
        raise RuntimeError(
            f"A porta {port} já está em uso. O backend do módulo Notas não foi iniciado."
        ) from error


def _wait_for_health(process: subprocess.Popen, port: int) -> None:
    deadline = monotonic() + HEALTH_TIMEOUT_SECONDS
    health_url = f"http://127.0.0.1:{port}/health"
    while monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                "O processo Node.js do módulo Notas foi encerrado durante a inicialização."
            )
        try:
            with urlopen(health_url, timeout=0.5) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if response.status == 200 and payload.get("success") is True:
                    return
        except (OSError, URLError, json.JSONDecodeError):
            pass
        sleep(HEALTH_RETRY_SECONDS)
    raise RuntimeError(
        "O backend do módulo Notas não respondeu ao health check durante a inicialização."
    )


def _terminate_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)
