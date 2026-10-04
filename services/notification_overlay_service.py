from __future__ import annotations

import gc
import logging
import queue
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from services.notification_stack import NotificationStack
from services.overlay_style import (
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


LOGGER = logging.getLogger(__name__)


class WindowsNotificationOverlayService:
    """Pilha visual de avisos da IRIS para o segundo plano."""

    WIDTH = 440
    MIN_HEIGHT = 116
    RIGHT_MARGIN = 24
    BOTTOM_MARGIN = 24
    LAYER_OFFSET = 12
    LOGO_PATH = Path(__file__).resolve().parent.parent / "assets/images/logo_transparent.png"

    def __init__(
        self, platform: str | None = None, *, on_open: Callable[[], None] | None = None,
    ) -> None:
        self.platform = platform or sys.platform
        self.on_open = on_open
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
                target=self._run, name="iris-notification-overlay", daemon=True,
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

    def hide_all(self) -> None:
        if self.available:
            self._commands.put(("clear", "", ""))

    def show_error(self, title: str, message: str) -> bool:
        if not self.available:
            return False
        self._commands.put((
            "error",
            " ".join(title.strip().split()) or "Erro na IRIS",
            " ".join(message.strip().split()),
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
            root.attributes("-alpha", 0.97)
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
            stack = NotificationStack()
            scroll = 0
            max_scroll = 0
            front_top = 0
            pointer_inside = False
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

            def draw() -> None:
                nonlocal scroll, max_scroll, front_top
                layers = stack.layers()
                if not layers:
                    set_close_hover(False)
                    root.withdraw()
                    return
                max_height = max(
                    self.MIN_HEIGHT,
                    root.winfo_screenheight() - self.BOTTOM_MARGIN * 2,
                )
                height, max_scroll, front_top = self._render(
                    canvas, layers, logo,
                    close_hover_image if close_hovered else close_image,
                    scroll=scroll, max_height=max_height,
                )
                if scroll > max_scroll:
                    scroll = max_scroll
                    height, max_scroll, front_top = self._render(
                        canvas, layers, logo,
                        close_hover_image if close_hovered else close_image,
                        scroll=scroll, max_height=max_height,
                    )
                left = max(0, root.winfo_screenwidth() - self.WIDTH - self.RIGHT_MARGIN)
                top = max(0, root.winfo_screenheight() - height - self.BOTTOM_MARGIN)
                root.geometry(f"{self.WIDTH}x{height}+{left}+{top}")
                root.deiconify()
                show_without_activation(root.winfo_id(), left, top)

            def on_click(event) -> None:
                nonlocal scroll
                if event.y < front_top:
                    return
                if is_close_hit(event.x, event.y, self.WIDTH, top=front_top):
                    stack.dismiss_front()
                    scroll = 0
                    if pointer_inside:
                        stack.start_hover()
                    draw()
                elif self.on_open is not None:
                    try:
                        self.on_open()
                    except Exception:
                        LOGGER.exception("Não foi possível abrir a IRIS pelo Notify.")

            def on_enter(_event) -> None:
                nonlocal pointer_inside
                pointer_inside = True
                stack.start_hover()

            def on_leave(_event) -> None:
                nonlocal pointer_inside
                pointer_inside = False
                stack.end_hover()
                set_close_hover(False)

            def on_motion(event) -> None:
                set_close_hover(is_close_hit(event.x, event.y, self.WIDTH, top=front_top))

            def on_wheel(event) -> None:
                nonlocal scroll
                if max_scroll <= 0:
                    return
                scroll = max(0, min(max_scroll, scroll - int(event.delta / 120) * 32))
                draw()

            canvas.bind("<Button-1>", on_click)
            canvas.bind("<Enter>", on_enter)
            canvas.bind("<Leave>", on_leave)
            canvas.bind("<Motion>", on_motion)
            canvas.bind("<MouseWheel>", on_wheel)

            def poll() -> None:
                nonlocal scroll
                changed = False
                try:
                    while True:
                        action, title, message = self._commands.get_nowait()
                        if action == "stop":
                            root.quit()
                            return
                        if action == "clear":
                            stack.clear()
                            scroll = 0
                            changed = True
                        elif action == "error":
                            stack.push(title, message)
                            if pointer_inside:
                                stack.start_hover()
                            scroll = 0
                            changed = True
                except queue.Empty:
                    pass
                before = stack.front
                stack.prune()
                if changed or stack.front is not before:
                    draw()
                root.after(50, poll)

            root.after(50, poll)
            root.mainloop()
            del logo
            root.destroy()
            gc.collect()
        except Exception:
            LOGGER.exception("Não foi possível iniciar o Notify da IRIS.")
        finally:
            with self._lock:
                if self._thread is threading.current_thread():
                    self._thread = None

    def _render(
        self, canvas, layers, logo, close_image, *, scroll: int, max_height: int,
    ) -> tuple[int, int, int]:
        canvas.delete("all")
        front = layers[0]
        front_top = self.LAYER_OFFSET * (len(layers) - 1)
        title = front.title + (f" ({front.count})" if front.count > 1 else "")
        title_item = canvas.create_text(
            72, front_top + 20 - scroll, text=title, fill=GLASS_TEXT,
            anchor="nw", width=self.WIDTH - 136,
            font=("Segoe UI Variable Display", 12, "bold"),
        )
        title_box = canvas.bbox(title_item) or (72, front_top + 20 - scroll, 72, front_top + 40 - scroll)
        message_y = title_box[3] + 8
        message_item = canvas.create_text(
            72, message_y, text=front.message or "—", fill=GLASS_MUTED,
            anchor="nw", width=self.WIDTH - 102,
            font=("Segoe UI Variable Text", 10),
        )
        message_box = canvas.bbox(message_item) or (72, message_y, 72, message_y + 20)
        full_card_height = max(self.MIN_HEIGHT, message_box[3] + scroll - front_top + 22)
        height = min(max_height, full_card_height + front_top)
        max_scroll = max(0, full_card_height + front_top - height)
        canvas.configure(height=height)
        for layer in range(len(layers) - 1, 0, -1):
            peek_top = front_top - self.LAYER_OFFSET * layer
            rounded_rectangle(
                canvas, 3, peek_top + 2, self.WIDTH - 3, height - 3, 18,
                fill=GLASS_BACKGROUND, outline=GLASS_BORDER, width=1,
            )
        background = rounded_rectangle(
            canvas, 3, front_top + 2, self.WIDTH - 3, height - 3, 18,
            fill=GLASS_BACKGROUND, outline="#E68891", width=2,
        )
        canvas.tag_lower(background)
        # Older cards must remain behind the front card.
        for item in canvas.find_all():
            if item not in {title_item, message_item, background}:
                canvas.tag_lower(item, background)
        if logo is not None:
            canvas.create_image(36, front_top + 36, image=logo)
        else:
            canvas.create_oval(
                17, front_top + 17, 55, front_top + 55,
                fill="#FFD0D3", outline="",
            )
            canvas.create_text(36, front_top + 36, text="!", fill=GLASS_TEXT)
        canvas.create_image(
            self.WIDTH - 33, front_top + 30, image=close_image, tags=("close",),
        )
        if max_scroll:
            canvas.create_text(
                self.WIDTH - 29, height - 17, text="↕", fill=GLASS_MUTED,
                font=("Segoe UI", 12),
            )
        return height, max_scroll, front_top

    def _load_logo(self, root):
        try:
            from PIL import Image, ImageTk

            with Image.open(self.LOGO_PATH) as source:
                logo = source.convert("RGBA")
                logo.thumbnail((44, 44), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(logo, master=root)
        except Exception:
            LOGGER.exception("Não foi possível carregar a logo do Notify da IRIS.")
            return None
