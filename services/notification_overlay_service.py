from __future__ import annotations

import ctypes
import gc
import logging
import queue
import sys
import threading
from pathlib import Path


LOGGER = logging.getLogger(__name__)


class WindowsNotificationOverlayService:
    """Toast próprio da IRIS para mensagens que não podem ser perdidas."""

    WIDTH = 440
    HEIGHT = 116
    RIGHT_MARGIN = 24
    BOTTOM_MARGIN = 24
    BACKGROUND = "#24212A"
    ERROR = "#EF5B64"
    TEXT = "#FFFFFF"
    TEXT_MUTED = "#C9C5CF"
    TRANSPARENT = "#010203"
    LOGO_PATH = (
        Path(__file__).resolve().parent.parent
        / "assets/images/logo_transparent.png"
    )

    def __init__(self, platform: str | None = None) -> None:
        self.platform = platform or sys.platform
        self._commands: queue.SimpleQueue[tuple[str, str, str]] = queue.SimpleQueue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> bool:
        if self.platform != "win32":
            return False
        with self._lock:
            if self.available:
                return True
            self._thread = threading.Thread(
                target=self._run,
                name="iris-notification-overlay",
                daemon=True,
            )
            self._thread.start()
        return True

    def stop(self) -> None:
        with self._lock:
            thread, self._thread = self._thread, None
        if thread is None:
            return
        self._commands.put(("stop", "", ""))
        if thread is not threading.current_thread():
            thread.join(timeout=1)

    def show_error(self, title: str, message: str) -> bool:
        return self._show("error", title, message)

    def _show(self, kind: str, title: str, message: str) -> bool:
        if not self.available:
            return False
        normalized_title = " ".join(title.strip().split()) or "Erro na IRIS"
        normalized_message = " ".join(message.strip().split())
        self._commands.put((kind, normalized_title, normalized_message))
        return True

    def _run(self) -> None:
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            root.overrideredirect(True)
            root.configure(bg=self.TRANSPARENT)
            root.attributes("-topmost", True)
            root.attributes("-transparentcolor", self.TRANSPARENT)
            root.attributes("-alpha", 0.98)

            canvas = tk.Canvas(
                root,
                width=self.WIDTH,
                height=self.HEIGHT,
                bg=self.TRANSPARENT,
                highlightthickness=0,
            )
            canvas.pack()
            root.update_idletasks()
            self._apply_windows_styles(root.winfo_id())
            images = {"logo": self._load_logo(root)}
            hide_job: str | None = None

            def hide() -> None:
                nonlocal hide_job
                hide_job = None
                root.withdraw()

            def show(title: str, message: str, *, error: bool) -> None:
                nonlocal hide_job
                if hide_job is not None:
                    root.after_cancel(hide_job)
                self._render(
                    canvas,
                    title,
                    message,
                    images["logo"],
                    error=error,
                )
                x = max(
                    0,
                    root.winfo_screenwidth() - self.WIDTH - self.RIGHT_MARGIN,
                )
                y = max(
                    0,
                    root.winfo_screenheight() - self.HEIGHT - self.BOTTOM_MARGIN,
                )
                root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
                root.deiconify()
                self._show_without_activation(root.winfo_id(), x, y)
                hide_job = root.after(6500, hide)

            def poll() -> None:
                try:
                    while True:
                        action, title, message = self._commands.get_nowait()
                        if action == "stop":
                            root.quit()
                            return
                        if action == "error":
                            show(title, message, error=True)
                except queue.Empty:
                    pass
                root.after(40, poll)

            root.after(40, poll)
            root.mainloop()
            logo_image = images.pop("logo", None)
            if logo_image is not None:
                del logo_image
                gc.collect()
            root.destroy()
            tk._default_root = None
            del canvas
            del root
            gc.collect()
        except Exception:
            LOGGER.exception("Não foi possível iniciar o toast próprio da IRIS.")
        finally:
            with self._lock:
                if self._thread is threading.current_thread():
                    self._thread = None

    def _render(
        self,
        canvas,
        title: str,
        message: str,
        logo_image,
        *,
        error: bool,
    ) -> None:
        canvas.delete("all")
        self._rounded_rectangle(
            canvas,
            3,
            3,
            self.WIDTH - 3,
            self.HEIGHT - 3,
            20,
            color=self.ERROR,
        )
        if logo_image is not None:
            canvas.create_image(38, 38, image=logo_image)
        canvas.create_text(
            72,
            25,
            text=title,
            fill=self.TEXT,
            anchor="w",
            font=("Segoe UI Variable Display", 12, "bold"),
        )
        canvas.create_text(
            72,
            50,
            text=message,
            fill=self.TEXT_MUTED,
            anchor="nw",
            width=self.WIDTH - 96,
            font=("Segoe UI Variable Text", 9),
        )

    def _rounded_rectangle(
        self, canvas, x1, y1, x2, y2, radius, *, color: str
    ) -> None:
        points = (
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        )
        canvas.create_polygon(
            points,
            smooth=True,
            splinesteps=24,
            fill=self.BACKGROUND,
            outline=color,
            width=2,
        )

    def _load_logo(self, root):
        try:
            from PIL import Image, ImageTk

            with Image.open(self.LOGO_PATH) as source:
                logo = source.convert("RGBA")
                logo.thumbnail((44, 44), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(logo, master=root)
        except Exception:
            LOGGER.exception("Não foi possível carregar a logo do toast da IRIS.")
            return None

    @staticmethod
    def _apply_windows_styles(window_handle: int) -> None:
        user32 = ctypes.windll.user32
        extended_style = user32.GetWindowLongW(window_handle, -20)
        extended_style |= 0x00000080 | 0x00000020 | 0x08000000
        user32.SetWindowLongW(window_handle, -20, extended_style)

    @staticmethod
    def _show_without_activation(window_handle: int, left: int, top: int) -> None:
        ctypes.windll.user32.SetWindowPos(
            window_handle,
            -1,
            left,
            top,
            0,
            0,
            0x0001 | 0x0010 | 0x0040,
        )
