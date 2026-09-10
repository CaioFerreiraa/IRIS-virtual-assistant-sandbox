from __future__ import annotations

import logging
import os
import sys


LOGGER = logging.getLogger(__name__)


class WindowsSettingsService:
    NOTIFICATIONS_URI = "ms-settings:notifications"

    def __init__(self, platform: str | None = None) -> None:
        self.platform = platform or sys.platform

    def open_notifications(self) -> bool:
        if self.platform != "win32":
            return False
        try:
            os.startfile(self.NOTIFICATIONS_URI)
            return True
        except Exception:
            LOGGER.exception(
                "Não foi possível abrir as configurações de notificações do Windows."
            )
            return False
