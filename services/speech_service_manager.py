from __future__ import annotations

import threading
from collections.abc import Callable

from services.speech_service import (
    FasterWhisperSpeechService,
    RealtimeSpeechService,
    SpeechEvent,
    SpeechEventCallback,
    SpeechEventKind,
    SpeechService,
)
from services.voice_settings import VoiceSettings


class SpeechServiceManager:
    """Mantém um único backend de voz pronto durante o ciclo da aplicação."""

    def __init__(self):
        self._service: SpeechService | None = None
        self._subscribers: list[SpeechEventCallback] = []
        self._lock = threading.RLock()
        self._reconfigure_lock = threading.Lock()
        self._configuration_version = 0
        self.last_event: SpeechEvent | None = None

    def prepare(self, settings: VoiceSettings) -> None:
        self.apply_settings(settings)

    def apply_settings(self, settings: VoiceSettings) -> None:
        settings.validate()
        with self._lock:
            self._configuration_version += 1
            configuration_version = self._configuration_version
            self.last_event = None

        threading.Thread(
            target=self._replace_service,
            args=(settings, configuration_version),
            name="SpeechServiceReconfigure",
            daemon=True,
        ).start()

    def subscribe(self, callback: SpeechEventCallback) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    def clear_subscribers(self) -> None:
        with self._lock:
            self._subscribers.clear()

    def deactivate_command(self) -> None:
        with self._lock:
            service = self._service
        if service is not None:
            service.deactivate_command()

    def shutdown(self) -> None:
        with self._lock:
            self._configuration_version += 1
            service = self._service
            self._service = None
        if service is not None:
            service.stop()

    def _replace_service(self, settings: VoiceSettings, configuration_version: int) -> None:
        # Serializa reinicializações sem bloquear a thread de eventos do Flet.
        with self._reconfigure_lock:
            with self._lock:
                if configuration_version != self._configuration_version:
                    return
                previous = self._service
                self._service = None

            if previous is not None:
                previous.stop()

            with self._lock:
                if configuration_version != self._configuration_version or not settings.enabled:
                    return

                service_class = (
                    RealtimeSpeechService
                    if settings.mode == "realtime"
                    else FasterWhisperSpeechService
                )
                service = service_class(settings, self._publish)
                self._service = service
                service.start()

    def _publish(self, event: SpeechEvent) -> None:
        if not (
            event.kind == SpeechEventKind.STOPPED
            and self.last_event is not None
            and self.last_event.kind == SpeechEventKind.ERROR
        ):
            self.last_event = event
        with self._lock:
            subscribers = tuple(self._subscribers)
        for callback in subscribers:
            callback(event)
