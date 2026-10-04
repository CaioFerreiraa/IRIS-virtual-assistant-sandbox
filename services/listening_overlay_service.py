from __future__ import annotations

import gc
import logging
import queue
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

from services.overlay_style import (
    GLASS_ACCENT,
    GLASS_BACKGROUND,
    GLASS_BORDER,
    GLASS_MUTED,
    GLASS_TEXT,
    TRANSPARENT,
    close_icon,
    is_close_hit,
    make_nonactivating,
    rounded_rectangle,
    show_without_activation,
)
from services.speech_service import SpeechEvent, SpeechEventKind, VoiceCommandStatus


LOGGER = logging.getLogger(__name__)


class WindowsListeningOverlayService:
    """HUD claro e não focável para comandos de voz no Windows."""

    WIDTH = 480
    MIN_HEIGHT = 76
    BOTTOM_MARGIN = 64
    ENTRANCE_DISTANCE = 16
    ENTRANCE_DURATION = 0.16
    LOGO_PATH = Path(__file__).resolve().parent.parent / "assets/images/logo_transparent.png"

    def __init__(
        self,
        platform: str | None = None,
        *,
        on_cancel_listening: Callable[[], None] | None = None,
    ) -> None:
        self.platform = platform or sys.platform
        self.on_cancel_listening = on_cancel_listening
        self._commands: queue.SimpleQueue[tuple[str, str, str]] = queue.SimpleQueue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._dismissed_session = False

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
                target=self._run, name="iris-listening-overlay", daemon=True,
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

    def hide(self) -> None:
        if self.available:
            self._commands.put(("hide_now", "", ""))

    def on_speech_event(self, event: SpeechEvent) -> None:
        if not self.available:
            return
        if event.kind == SpeechEventKind.ACTIVATED:
            with self._lock:
                self._dismissed_session = False
            self._commands.put(("show", "Ouvindo…", "Fale seu comando"))
        elif event.kind in {SpeechEventKind.PARTIAL, SpeechEventKind.FINAL}:
            with self._lock:
                if self._dismissed_session:
                    return
            text = " ".join(event.text.strip().split()) or "Ouvindo…"
            if event.kind == SpeechEventKind.FINAL and event.command_status == VoiceCommandStatus.UNKNOWN:
                self._commands.put(("unmatched", text, "Não encontrei módulo. Tente novamente."))
            else:
                self._commands.put(("show", text, "IRIS está ouvindo"))
        elif event.kind == SpeechEventKind.ERROR:
            message = " ".join(event.message.strip().split()) or "Voz indisponível"
            self._commands.put(("error", message, "Não foi possível continuar"))
        elif event.kind in {SpeechEventKind.DEACTIVATED, SpeechEventKind.STOPPED}:
            self._commands.put(("hide", "", ""))

    def show_feedback(self, title: str, message: str, *, error: bool) -> bool:
        if not self.available:
            return False
        self._commands.put((
            "error" if error else "result",
            " ".join(title.strip().split()) or "IRIS",
            " ".join(message.strip().split()) or (
                "Tente novamente" if error else "Módulo executado com sucesso."
            ),
        ))
        return True

    def _run(self) -> None:
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            root.overrideredirect(True)
            root.configure(bg=TRANSPARENT)
            root.attributes("-topmost", True)
            root.attributes("-transparentcolor", TRANSPARENT)
            root.attributes("-alpha", 0.96)
            canvas = tk.Canvas(
                root, width=self.WIDTH, height=self.MIN_HEIGHT,
                bg=TRANSPARENT, highlightthickness=0,
            )
            canvas.pack()
            root.update_idletasks()
            make_nonactivating(root.winfo_id())
            logo = self._load_logo(root)
            close_image = close_icon(root)
            close_hover_image = close_icon(root, hover=True)
            hide_job: str | None = None
            hint_job: str | None = None
            animation_job: str | None = None
            animation_start: float | None = None
            feedback_until = 0.0
            current: tuple[str, str, str] | None = None
            scroll = 0
            max_scroll = 0
            listening = False
            close_hovered = False

            def set_close_hover(hovered: bool) -> None:
                nonlocal close_hovered
                if hovered == close_hovered:
                    return
                close_hovered = hovered
                canvas.configure(cursor="hand2" if hovered else "")
                canvas.itemconfigure(
                    "close", image=close_hover_image if hovered else close_image,
                )

            def cancel_animation() -> None:
                nonlocal animation_job, animation_start
                if animation_job is not None:
                    root.after_cancel(animation_job)
                    animation_job = None
                animation_start = None

            def cancel_hide() -> None:
                nonlocal hide_job
                if hide_job is not None:
                    root.after_cancel(hide_job)
                    hide_job = None

            def cancel_hint() -> None:
                nonlocal hint_job
                if hint_job is not None:
                    root.after_cancel(hint_job)
                    hint_job = None

            def hide() -> None:
                nonlocal current, listening
                cancel_hide()
                cancel_hint()
                cancel_animation()
                set_close_hover(False)
                current = None
                listening = False
                root.withdraw()

            def schedule_hide(delay_ms: int) -> None:
                nonlocal hide_job
                cancel_hide()
                hide_job = root.after(delay_ms, hide)

            def draw() -> None:
                nonlocal max_scroll, scroll, animation_start
                if current is None:
                    return
                action, title, subtitle = current
                max_height = max(self.MIN_HEIGHT, root.winfo_screenheight() - self.BOTTOM_MARGIN * 2)
                height, max_scroll = self._render(
                    canvas, title, subtitle, logo,
                    close_hover_image if close_hovered else close_image,
                    error=action == "error", scroll=scroll, max_height=max_height,
                )
                if scroll > max_scroll:
                    scroll = max_scroll
                    height, max_scroll = self._render(
                        canvas, title, subtitle, logo,
                        close_hover_image if close_hovered else close_image,
                        error=action == "error", scroll=scroll, max_height=max_height,
                    )
                left = max(0, (root.winfo_screenwidth() - self.WIDTH) // 2)
                top = max(0, root.winfo_screenheight() - height - self.BOTTOM_MARGIN)
                if animation_start is not None:
                    progress = min(1.0, (time.monotonic() - animation_start) / self.ENTRANCE_DURATION)
                    if progress >= 1.0:
                        animation_start = None
                    else:
                        top += round(self.ENTRANCE_DISTANCE * (1.0 - progress) ** 3)
                root.geometry(f"{self.WIDTH}x{height}+{left}+{top}")
                root.deiconify()
                show_without_activation(root.winfo_id(), left, top)

            def animate_step() -> None:
                nonlocal animation_job
                animation_job = None
                if current is None or animation_start is None:
                    return
                draw()
                if animation_start is not None:
                    animation_job = root.after(16, animate_step)

            def show(action: str, title: str, subtitle: str) -> None:
                nonlocal current, scroll, listening, animation_start, animation_job
                cancel_hide()
                cancel_hint()
                start_entrance = current is None and action == "show"
                if action != "show":
                    cancel_animation()
                current = (action, title, subtitle)
                scroll = 0
                listening = action in {"show", "unmatched"}
                if start_entrance:
                    animation_start = time.monotonic()
                draw()
                if start_entrance and animation_start is not None:
                    animation_job = root.after(16, animate_step)

            def on_click(event) -> None:
                if not is_close_hit(event.x, event.y, self.WIDTH):
                    return
                was_listening = listening
                if was_listening:
                    with self._lock:
                        self._dismissed_session = True
                hide()
                if was_listening and self.on_cancel_listening is not None:
                    try:
                        self.on_cancel_listening()
                    except Exception:
                        LOGGER.exception("Não foi possível cancelar a escuta pelo HUD.")

            def on_wheel(event) -> None:
                nonlocal scroll
                if max_scroll <= 0:
                    return
                scroll = max(0, min(max_scroll, scroll - int(event.delta / 120) * 32))
                draw()

            def on_motion(event) -> None:
                set_close_hover(is_close_hit(event.x, event.y, self.WIDTH))

            def return_to_listening() -> None:
                nonlocal hint_job
                hint_job = None
                if current is not None:
                    show("show", "Ouvindo…", "Fale seu comando")

            canvas.bind("<Button-1>", on_click)
            canvas.bind("<MouseWheel>", on_wheel)
            canvas.bind("<Motion>", on_motion)
            canvas.bind("<Leave>", lambda _event: set_close_hover(False))

            def poll() -> None:
                nonlocal feedback_until, hint_job
                try:
                    while True:
                        action, title, subtitle = self._commands.get_nowait()
                        if action == "stop":
                            root.quit()
                            return
                        if action in {"show", "unmatched", "error", "result"}:
                            show(action, title, subtitle)
                            if action == "unmatched":
                                hint_job = root.after(1800, return_to_listening)
                            elif action in {"error", "result"}:
                                duration = 3500 if action == "error" else 2500
                                feedback_until = time.monotonic() + duration / 1000
                                schedule_hide(duration)
                        elif action == "hide_now":
                            hide()
                        elif action == "hide":
                            remaining = feedback_until - time.monotonic()
                            schedule_hide(max(900, int(remaining * 1000)) if remaining > 0 else 900)
                except queue.Empty:
                    pass
                root.after(40, poll)

            root.after(40, poll)
            root.mainloop()
            del logo
            root.destroy()
            gc.collect()
        except Exception:
            LOGGER.exception("Não foi possível iniciar o indicador flutuante da IRIS.")
        finally:
            with self._lock:
                if self._thread is threading.current_thread():
                    self._thread = None

    def _render(
        self, canvas, title: str, subtitle: str, logo, close_image,
        *, error: bool, scroll: int, max_height: int,
    ) -> tuple[int, int]:
        canvas.delete("all")
        accent = "#E68891" if error else GLASS_ACCENT
        title_item = canvas.create_text(
            74, 20 - scroll, text=title, fill=GLASS_TEXT, anchor="nw",
            width=self.WIDTH - 140, font=("Segoe UI Variable Display", 12, "bold"),
        )
        title_box = canvas.bbox(title_item) or (74, 20 - scroll, 74, 40 - scroll)
        subtitle_y = title_box[3] + 8
        subtitle_item = canvas.create_text(
            74, subtitle_y, text=subtitle, fill=GLASS_MUTED, anchor="nw",
            width=self.WIDTH - 140, font=("Segoe UI Variable Text", 10),
        )
        subtitle_box = canvas.bbox(subtitle_item) or (74, subtitle_y, 74, subtitle_y + 20)
        full_height = max(self.MIN_HEIGHT, subtitle_box[3] + scroll + 20)
        height = min(max_height, full_height)
        max_scroll = max(0, full_height - height)
        canvas.configure(height=height, scrollregion=(0, 0, self.WIDTH, height))
        background = rounded_rectangle(
            canvas, 3, 3, self.WIDTH - 3, height - 3, 20,
            fill=GLASS_BACKGROUND, outline=accent if error else GLASS_BORDER, width=2,
        )
        canvas.tag_lower(background)
        if logo is not None:
            canvas.create_image(38, 38, image=logo)
        else:
            canvas.create_oval(18, 18, 58, 58, fill=GLASS_BORDER, outline="")
            canvas.create_text(38, 38, text="I", fill=GLASS_TEXT, font=("Segoe UI", 16, "bold"))
        canvas.create_image(self.WIDTH - 33, 30, image=close_image, tags=("close",))
        if max_scroll:
            canvas.create_text(
                self.WIDTH - 30, height - 17, text="↕", fill=GLASS_MUTED,
                font=("Segoe UI", 12),
            )
        return height, max_scroll

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
