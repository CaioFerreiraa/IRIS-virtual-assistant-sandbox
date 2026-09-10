from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Protocol

from services.speech_service import SpeechEvent


LOGGER = logging.getLogger(__name__)


class TrayVoiceState(Enum):
    UNAVAILABLE = "unavailable"
    READY = "ready"
    ACTIVE = "active"


class SpeechManagerState(Protocol):
    current_settings: object
    session_paused: bool
    backend_ready: bool
    backend_error: bool
    microphone_available: bool | None
    activity_state: str


def voice_state_from_manager(manager: SpeechManagerState) -> TrayVoiceState:
    settings_enabled = bool(getattr(manager.current_settings, "enabled", False))
    if (
        not settings_enabled
        or manager.session_paused
        or not manager.backend_ready
        or manager.backend_error
        or manager.microphone_available is False
    ):
        return TrayVoiceState.UNAVAILABLE
    if manager.activity_state == "active":
        return TrayVoiceState.ACTIVE
    return TrayVoiceState.READY


class WindowsSystemTrayService:
    """Adapter isolado para a bandeja nativa do Windows via pystray."""

    ICON_PATH = Path(__file__).resolve().parent.parent / "assets/images/logo_transparent.png"
    NOTIFICATION_DELAY_SECONDS = 0.3
    COLORS = {
        TrayVoiceState.UNAVAILABLE: "#7B8190",
        TrayVoiceState.READY: "#8B6FC0",
        TrayVoiceState.ACTIVE: "#67B98A",
    }
    TOOLTIPS = {
        TrayVoiceState.UNAVAILABLE: "IRIS · voz desativada, pausada ou indisponível",
        TrayVoiceState.READY: "IRIS · aguardando “IRIS”",
        TrayVoiceState.ACTIVE: "IRIS · ouvindo comando",
    }

    def __init__(
        self,
        speech_manager,
        *,
        on_open: Callable[[], None],
        on_exit: Callable[[], None],
        platform: str | None = None,
    ) -> None:
        self.speech_manager = speech_manager
        self.on_open = on_open
        self.on_exit = on_exit
        self.platform = platform or sys.platform
        self._icon = None
        self._unsubscribe: Callable[[], None] | None = None
        self._notification_timers: set[threading.Timer] = set()
        self._notification_lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self._icon is not None

    def start(self) -> bool:
        if self.available:
            return True
        if self.platform != "win32":
            return False
        try:
            import pystray

            state = voice_state_from_manager(self.speech_manager)
            self._icon = pystray.Icon(
                "IRIS",
                self._build_icon(state),
                self.TOOLTIPS[state],
                menu=pystray.Menu(
                    pystray.MenuItem("Abrir IRIS", self._open, default=True),
                    pystray.MenuItem(self._voice_label, self._toggle_voice),
                    pystray.MenuItem("Sair da IRIS", self._exit),
                ),
            )
            self._icon.run_detached()
            self._unsubscribe = self.speech_manager.subscribe(
                self._on_speech_event,
                persistent=True,
            )
            return True
        except Exception:
            LOGGER.exception("Não foi possível iniciar a bandeja da IRIS.")
            self.stop()
            return False

    def stop(self) -> None:
        with self._notification_lock:
            notification_timers = tuple(self._notification_timers)
            self._notification_timers.clear()
        for timer in notification_timers:
            timer.cancel()
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        icon, self._icon = self._icon, None
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                LOGGER.exception("Não foi possível encerrar a bandeja da IRIS.")

    def refresh(self) -> None:
        icon = self._icon
        if icon is None:
            return
        state = voice_state_from_manager(self.speech_manager)
        icon.icon = self._build_icon(state)
        icon.title = self.TOOLTIPS[state]
        icon.update_menu()

    def notify(self, message: str, *, title: str = "IRIS") -> bool:
        icon = self._icon
        if icon is None or not getattr(icon, "HAS_NOTIFICATION", False):
            return False

        timer: threading.Timer

        def send() -> None:
            try:
                if self._icon is icon:
                    icon.notify(message[:255], title[:63])
            except Exception:
                LOGGER.exception("Não foi possível exibir uma notificação da IRIS.")
            finally:
                with self._notification_lock:
                    self._notification_timers.discard(timer)

        timer = threading.Timer(self.NOTIFICATION_DELAY_SECONDS, send)
        timer.daemon = True
        with self._notification_lock:
            self._notification_timers.add(timer)
        timer.start()
        return True

    def _voice_label(self, _item) -> str:
        return "Ativar voz" if self.speech_manager.session_paused else "Pausar voz"

    def _open(self, _icon=None, _item=None) -> None:
        self.on_open()

    def _toggle_voice(self, _icon=None, _item=None) -> None:
        self.speech_manager.set_session_paused(
            not self.speech_manager.session_paused
        )
        self.refresh()

    def _exit(self, _icon=None, _item=None) -> None:
        self.on_exit()

    def _on_speech_event(self, _event: SpeechEvent) -> None:
        self.refresh()

    def _build_icon(self, state: TrayVoiceState):
        from PIL import Image, ImageDraw

        with Image.open(self.ICON_PATH) as source:
            logo = source.convert("RGBA")

        logo.thumbnail((60, 60), Image.Resampling.LANCZOS)
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        image.alpha_composite(
            logo,
            ((image.width - logo.width) // 2, (image.height - logo.height) // 2),
        )

        draw = ImageDraw.Draw(image)
        if state is TrayVoiceState.ACTIVE:
            draw.ellipse((2, 2, 61, 61), outline=self.COLORS[state], width=5)
            draw.ellipse((42, 42, 63, 63), fill="white")
            draw.ellipse((45, 45, 60, 60), fill=self.COLORS[state])
            return image

        draw.ellipse((44, 44, 63, 63), fill="white")
        draw.ellipse((47, 47, 60, 60), fill=self.COLORS[state])
        return image
