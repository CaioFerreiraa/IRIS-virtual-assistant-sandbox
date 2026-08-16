from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import traceback


LOGGER = logging.getLogger(__name__)


def append_module_error_log(
    module_folder: Path,
    stage: str,
    error: Exception,
) -> Path:
    log_path = module_folder.resolve() / "module.log"
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    traceback_text = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    entry = (
        f"[{timestamp}]\n"
        f"Etapa: {stage}\n"
        f"Tipo da exceção: {type(error).__name__}\n"
        f"Mensagem: {error}\n"
        f"Traceback:\n{traceback_text}\n"
    )
    try:
        with log_path.open("a", encoding="utf-8", newline="\n") as log_file:
            log_file.write(entry)
    except Exception:
        LOGGER.exception(
            "Não foi possível gravar module.log para o módulo em %s.",
            module_folder,
        )
    return log_path
