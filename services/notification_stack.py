from __future__ import annotations

import time
from dataclasses import dataclass
from collections.abc import Callable


@dataclass
class Notification:
    title: str
    message: str
    expires_at: float
    count: int = 1


class NotificationStack:
    """Mostra o aviso mais novo e conserva apenas avisos ainda válidos."""

    DURATION_SECONDS = 6.5

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._items: list[Notification] = []
        self._hover_started: float | None = None
        self._last_arrival: tuple[str, str] | None = None

    def clear(self) -> None:
        self._items.clear()
        self._hover_started = None
        self._last_arrival = None

    def prune(self) -> None:
        now = self._clock()
        front = self.front
        self._items = [
            item for item in self._items
            if item.expires_at > now or (item is front and self._hover_started is not None)
        ]
        if not self._items:
            self._hover_started = None

    @property
    def front(self) -> Notification | None:
        return self._items[-1] if self._items else None

    def layers(self) -> tuple[Notification, ...]:
        self.prune()
        return tuple(reversed(self._items[-3:]))

    def push(self, title: str, message: str) -> None:
        self.end_hover()
        self.prune()
        now = self._clock()
        front = self.front
        key = (title, message)
        if front is not None and self._last_arrival == key and (front.title, front.message) == key:
            front.count += 1
            front.expires_at = now + self.DURATION_SECONDS
            return
        self._items.append(Notification(title, message, now + self.DURATION_SECONDS))
        self._last_arrival = key

    def dismiss_front(self) -> None:
        self._hover_started = None
        self._last_arrival = None
        if self._items:
            self._items.pop()
        self.prune()

    def start_hover(self) -> None:
        self.prune()
        if self.front is not None and self._hover_started is None:
            self._hover_started = self._clock()

    def end_hover(self) -> None:
        if self._hover_started is not None and self.front is not None:
            self.front.expires_at += self._clock() - self._hover_started
        self._hover_started = None
