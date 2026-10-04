from __future__ import annotations

import ctypes

from ui.theme.colors import PASTEL_DARK_PURPLE, PASTEL_PURPLE, TEXT_PRIMARY, TEXT_SECONDARY


GLASS_BACKGROUND = "#F8FBFF"
GLASS_BORDER = PASTEL_PURPLE
GLASS_TEXT = TEXT_PRIMARY
GLASS_MUTED = TEXT_SECONDARY
GLASS_ACCENT = PASTEL_DARK_PURPLE
TRANSPARENT = "#010203"


def close_icon(root, size: int = 32, *, hover: bool = False):
    """Draw a centered, antialiased close control for the Tk overlays."""
    from PIL import Image, ImageDraw, ImageTk

    scale = 4
    image = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    inset = scale
    draw.ellipse(
        (inset, inset, size * scale - inset - 1, size * scale - inset - 1),
        fill="#F0EAF8" if hover else GLASS_BACKGROUND,
        outline=GLASS_ACCENT if hover else GLASS_BORDER,
        width=scale,
    )
    center = (size * scale - 1) / 2
    arm = 4.5 * scale
    stroke = 2 * scale
    for start, end in (
        ((center - arm, center - arm), (center + arm, center + arm)),
        ((center + arm, center - arm), (center - arm, center + arm)),
    ):
        draw.line((start, end), fill=GLASS_TEXT, width=stroke)
        for x, y in (start, end):
            draw.ellipse(
                (x - stroke / 2, y - stroke / 2, x + stroke / 2, y + stroke / 2),
                fill=GLASS_TEXT,
            )
    return ImageTk.PhotoImage(
        image.resize((size, size), Image.Resampling.LANCZOS), master=root,
    )


def is_close_hit(x: int, y: int, width: int, *, top: int = 0) -> bool:
    return width - 52 <= x < width and top <= y < top + 52


def rounded_rectangle(canvas, x1: int, y1: int, x2: int, y2: int, radius: int, *, fill: str, outline: str, width: int = 1):
    points = (
        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
    )
    return canvas.create_polygon(
        points, smooth=True, splinesteps=24, fill=fill, outline=outline, width=width,
    )


def make_nonactivating(window_handle: int) -> None:
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongW(window_handle, -20)
    # Tool window and no-activate keep the overlay out of Alt+Tab without
    # making its close button click-through.
    user32.SetWindowLongW(window_handle, -20, style | 0x00000080 | 0x08000000)


def show_without_activation(window_handle: int, left: int, top: int) -> None:
    ctypes.windll.user32.SetWindowPos(
        window_handle, -1, left, top, 0, 0, 0x0001 | 0x0010 | 0x0020 | 0x0040,
    )
