from __future__ import annotations

import ctypes
import gc
import logging
import queue
import sys
import threading
import time
from pathlib import Path

from services.speech_service import SpeechEvent, SpeechEventKind


LOGGER = logging.getLogger(__name__)


class WindowsListeningOverlayService:
    """HUD nativo e não focável para acompanhar comandos de voz no Windows."""

    WIDTH = 480
    HEIGHT = 76
    MAX_RESULT_HEIGHT = 220
    BOTTOM_MARGIN = 64
    BACKGROUND = "#24212A"
    ACTIVE = "#67B98A"
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
                name="iris-listening-overlay",
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

    def on_speech_event(self, event: SpeechEvent) -> None:
        if not self.available:
            return
        if event.kind == SpeechEventKind.ACTIVATED:
            self._commands.put(("show", "Ouvindo…", "Fale seu comando"))
        elif event.kind in {SpeechEventKind.PARTIAL, SpeechEventKind.FINAL}:
            text = " ".join(event.text.strip().split()) or "Ouvindo…"
            self._commands.put(("show", text, "IRIS está ouvindo"))
        elif event.kind == SpeechEventKind.ERROR:
            message = " ".join(event.message.strip().split()) or "Voz indisponível"
            self._commands.put(("error", message, "Não foi possível continuar"))
        elif event.kind in {SpeechEventKind.DEACTIVATED, SpeechEventKind.STOPPED}:
            self._commands.put(("hide", "", ""))

    def show_feedback(self, title: str, message: str, *, error: bool) -> bool:
        if not self.available:
            return False
        normalized_message = " ".join(message.strip().split())
        normalized_title = " ".join(title.strip().split())
        self._commands.put(
            (
                "error" if error else "result",
                (
                    "Não consegui executar o comando"
                    if error
                    else normalized_title or "IRIS"
                ),
                (
                    "Tente novamente"
                    if error
                    else normalized_message or "Módulo executado com sucesso."
                ),
            )
        )
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
            root.attributes("-alpha", 0.97)

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
            feedback_visible_until = 0.0

            def cancel_hide() -> None:
                nonlocal hide_job
                if hide_job is not None:
                    root.after_cancel(hide_job)
                    hide_job = None

            def hide() -> None:
                nonlocal hide_job
                hide_job = None
                root.withdraw()

            def schedule_hide(delay_ms: int) -> None:
                nonlocal hide_job
                cancel_hide()
                hide_job = root.after(delay_ms, hide)

            def show(
                text: str,
                subtitle: str,
                *,
                error: bool = False,
                result: bool = False,
            ) -> None:
                cancel_hide()
                height = self._render(
                    canvas,
                    text,
                    subtitle,
                    error=error,
                    result=result,
                    logo_image=images["logo"],
                )
                x = max(0, (root.winfo_screenwidth() - self.WIDTH) // 2)
                y = max(
                    0,
                    root.winfo_screenheight() - height - self.BOTTOM_MARGIN,
                )
                root.geometry(f"{self.WIDTH}x{height}+{x}+{y}")
                root.deiconify()
                self._show_without_activation(root.winfo_id(), x, y)

            def poll() -> None:
                nonlocal feedback_visible_until
                try:
                    while True:
                        action, text, subtitle = self._commands.get_nowait()
                        if action == "stop":
                            root.quit()
                            return
                        if action == "show":
                            show(text, subtitle)
                        elif action == "error":
                            feedback_visible_until = time.monotonic() + 3.5
                            show(text, subtitle, error=True)
                            schedule_hide(3500)
                        elif action == "result":
                            feedback_visible_until = time.monotonic() + 2.5
                            show(text, subtitle, result=True)
                            schedule_hide(2500)
                        elif action == "hide":
                            remaining = feedback_visible_until - time.monotonic()
                            schedule_hide(
                                max(900, int(remaining * 1000))
                                if remaining > 0
                                else 900
                            )
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
            LOGGER.exception("Não foi possível iniciar o indicador flutuante da IRIS.")
        finally:
            with self._lock:
                if self._thread is threading.current_thread():
                    self._thread = None

    def _render(
        self,
        canvas,
        text: str,
        subtitle: str,
        *,
        error: bool,
        result: bool,
        logo_image,
    ) -> int:
        canvas.delete("all")
        accent = self.ERROR if error else self.ACTIVE
        if logo_image is not None:
            canvas.create_image(38, 38, image=logo_image)
        else:
            canvas.create_oval(18, 18, 58, 58, fill=accent, outline="")
            canvas.create_text(
                38,
                38,
                text="I",
                fill=self.TEXT,
                font=("Segoe UI", 16, "bold"),
            )
        title_item = canvas.create_text(
            74,
            20 if result else 28,
            text=text if result else self._truncate(text, 52),
            fill=self.TEXT,
            anchor="nw" if result else "w",
            width=self.WIDTH - 104 if result else 0,
            font=("Segoe UI Variable Display", 12, "bold"),
        )
        title_box = canvas.bbox(title_item) or (74, 20, 74, 40)
        subtitle_y = title_box[3] + 8 if result else 50
        subtitle_item = canvas.create_text(
            74,
            subtitle_y,
            text=subtitle,
            fill=self.TEXT_MUTED,
            anchor="nw" if result else "w",
            width=self.WIDTH - 104 if result else 0,
            font=("Segoe UI Variable Text", 9),
        )
        subtitle_box = canvas.bbox(subtitle_item) or (74, subtitle_y, 74, subtitle_y)
        height = (
            min(self.MAX_RESULT_HEIGHT, max(self.HEIGHT, subtitle_box[3] + 20))
            if result
            else self.HEIGHT
        )
        canvas.configure(height=height)
        background = self._rounded_rectangle(
            canvas,
            3,
            3,
            self.WIDTH - 3,
            height - 3,
            20,
            outline=self.ERROR if error else "",
            width=2 if error else 0,
        )
        canvas.tag_lower(background)
        if not error:
            canvas.create_oval(
                self.WIDTH - 28,
                34,
                self.WIDTH - 20,
                42,
                fill=accent,
                outline="",
            )
        return height

    def _rounded_rectangle(
        self, canvas, x1, y1, x2, y2, radius, *, outline: str, width: int
    ) -> None:
        points = (
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        )
        return canvas.create_polygon(
            points,
            smooth=True,
            splinesteps=24,
            fill=self.BACKGROUND,
            outline=outline,
            width=width,
        )

    def _load_logo(self, root):
        try:
            from PIL import Image, ImageTk

            with Image.open(self.LOGO_PATH) as source:
                logo = source.convert("RGBA")
                logo.thumbnail((44, 44), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(logo, master=root)
        except Exception:
            LOGGER.exception("Não foi possível carregar a logo do indicador flutuante.")
            return None

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        return text if len(text) <= limit else f"{text[: limit - 1].rstrip()}…"

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
