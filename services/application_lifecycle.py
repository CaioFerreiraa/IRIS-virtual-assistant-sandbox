from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Protocol


class ShutdownResource(Protocol):
    def shutdown(self) -> None: ...


class TrayResource(Protocol):
    @property
    def available(self) -> bool: ...

    def stop(self) -> None: ...


class BackgroundResource(Protocol):
    def stop(self) -> None: ...


class ApplicationLifecycle:
    """Coordena ocultação e encerramento sem conhecer controles visuais."""

    def __init__(
        self,
        *,
        speech_manager: ShutdownResource,
        runtime_manager: ShutdownResource,
        tray_service: TrayResource,
        background_resources: tuple[BackgroundResource, ...] = (),
        hide_window: Callable[[], None],
        restore_window: Callable[[], None],
        close_window: Callable[[], None],
    ) -> None:
        self.speech_manager = speech_manager
        self.runtime_manager = runtime_manager
        self.tray_service = tray_service
        self.background_resources = background_resources
        self.hide_window = hide_window
        self.restore_window = restore_window
        self.close_window = close_window
        self._lock = threading.Lock()
        self._exiting = False

    def request_close(self) -> None:
        if self.tray_service.available:
            self.hide_window()
            return
        self.close_window()

    def restore(self) -> None:
        self.restore_window()

    def exit_application(self) -> None:
        with self._lock:
            if self._exiting:
                return
            self._exiting = True
        self.speech_manager.shutdown()
        self.runtime_manager.shutdown()
        for resource in self.background_resources:
            resource.stop()
        self.tray_service.stop()
        self.close_window()
