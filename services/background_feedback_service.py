from __future__ import annotations

from threading import RLock

from services.speech_service import SpeechEvent, SpeechEventKind, VoiceCommandStatus


NOTIFICATION_MODES = {"none", "iris", "windows"}
ERROR_TITLES = {"Erro no módulo", "Voz indisponível"}


class BackgroundFeedbackService:
    """Decide quando e por qual canal o feedback externo aparece."""

    def __init__(self, listening_overlay, notification_overlay, tray_service, *, mode: str):
        self.listening_overlay = listening_overlay
        self.notification_overlay = notification_overlay
        self.tray_service = tray_service
        self._lock = RLock()
        self._foreground = True
        self._mode = mode if mode in NOTIFICATION_MODES else "iris"
        self._active_event: SpeechEvent | None = None

    def set_foreground(self, foreground: bool) -> None:
        with self._lock:
            if self._foreground == foreground:
                return
            self._foreground = foreground
            if foreground:
                self.listening_overlay.hide()
                self.notification_overlay.hide_all()
                self.tray_service.clear_notifications()
            elif self._active_event is not None:
                self.listening_overlay.on_speech_event(self._active_event)

    def set_notification_mode(self, mode: str) -> None:
        if mode not in NOTIFICATION_MODES:
            raise ValueError("Canal de notificações inválido.")
        with self._lock:
            self._mode = mode
            self.notification_overlay.hide_all()
            self.tray_service.clear_notifications()

    def on_speech_event(self, event: SpeechEvent) -> None:
        with self._lock:
            if event.kind in {SpeechEventKind.ACTIVATED, SpeechEventKind.PARTIAL, SpeechEventKind.FINAL}:
                self._active_event = event
                if event.kind == SpeechEventKind.FINAL and event.command_status == VoiceCommandStatus.UNKNOWN:
                    self._active_event = SpeechEvent(
                        SpeechEventKind.ACTIVATED, session_id=event.session_id,
                    )
            elif event.kind in {SpeechEventKind.DEACTIVATED, SpeechEventKind.STOPPED, SpeechEventKind.ERROR}:
                self._active_event = None
            if not self._foreground:
                self.listening_overlay.on_speech_event(event)

    def notify(self, title: str, message: str) -> bool:
        with self._lock:
            if self._foreground:
                return False
            mode = self._mode
            is_error = title in ERROR_TITLES
            shown = self.listening_overlay.show_feedback(title, message, error=is_error)
            if not is_error:
                return shown
            if mode == "iris":
                return self.notification_overlay.show_error(title, message)
            if mode == "windows":
                return self.tray_service.show_notification(title, message)
            return shown
