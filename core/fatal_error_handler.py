from collections.abc import Callable
from functools import wraps
from typing import TypeVar

import flet as ft

from ui.shared.components.toaster_handler import ToasterHandler


T = TypeVar("T")


class FatalErrorHandler:
    def __init__(self, page: ft.Page, toaster_handler: ToasterHandler):
        self.page = page
        self.toaster_handler = toaster_handler
        self._is_handling_error = False

    def install(self) -> None:
        self.page.on_error = self.handle_page_error

    def guard_call(
        self,
        callback: Callable[..., T],
        *args,
        fallback: T | None = None,
        **kwargs,
    ) -> T | None:
        try:
            return callback(*args, **kwargs)
        except Exception as error:
            self.handle(error)
            return fallback

    def guard_callback(self, callback: Callable[..., T]) -> Callable[..., T | None]:
        @wraps(callback)
        def wrapped(*args, **kwargs) -> T | None:
            return self.guard_call(callback, *args, **kwargs)

        return wrapped

    def handle_page_error(self, event) -> None:
        error_message = getattr(event, "data", None) or str(event)
        self.handle(RuntimeError(error_message))

    def handle(self, error: Exception) -> None:
        print(error)

        if self._is_handling_error:
            return

        self._is_handling_error = True
        try:
            self.toaster_handler.show_error(
                message=str(error) or "Erro inesperado.",
                title="Erro inesperado",
            )
            self._redirect_home()
        finally:
            self._is_handling_error = False

    def _redirect_home(self) -> None:
        try:
            if (self.page.route or "/home") != "/home":
                self.page.go("/home")
            elif self.page.controls:
                self.page.update()
        except Exception as error:
            print(error)
