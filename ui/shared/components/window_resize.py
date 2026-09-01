from dataclasses import dataclass

import flet as ft


WINDOW_RESIZE_EDGE_SIZE = 6
WINDOW_RESIZE_CORNER_SIZE = 12


@dataclass(frozen=True)
class _ResizeHandleSpec:
    edge: ft.WindowResizeEdge
    cursor: ft.MouseCursor
    left: float | None = None
    top: float | None = None
    right: float | None = None
    bottom: float | None = None
    width: float | None = None
    height: float | None = None


_RESIZE_HANDLE_SPECS = (
    _ResizeHandleSpec(
        ft.WindowResizeEdge.TOP,
        ft.MouseCursor.RESIZE_UP_DOWN,
        left=WINDOW_RESIZE_CORNER_SIZE,
        top=0,
        right=WINDOW_RESIZE_CORNER_SIZE,
        height=WINDOW_RESIZE_EDGE_SIZE,
    ),
    _ResizeHandleSpec(
        ft.WindowResizeEdge.RIGHT,
        ft.MouseCursor.RESIZE_LEFT_RIGHT,
        top=WINDOW_RESIZE_CORNER_SIZE,
        right=0,
        bottom=WINDOW_RESIZE_CORNER_SIZE,
        width=WINDOW_RESIZE_EDGE_SIZE,
    ),
    _ResizeHandleSpec(
        ft.WindowResizeEdge.BOTTOM,
        ft.MouseCursor.RESIZE_UP_DOWN,
        left=WINDOW_RESIZE_CORNER_SIZE,
        right=WINDOW_RESIZE_CORNER_SIZE,
        bottom=0,
        height=WINDOW_RESIZE_EDGE_SIZE,
    ),
    _ResizeHandleSpec(
        ft.WindowResizeEdge.LEFT,
        ft.MouseCursor.RESIZE_LEFT_RIGHT,
        left=0,
        top=WINDOW_RESIZE_CORNER_SIZE,
        bottom=WINDOW_RESIZE_CORNER_SIZE,
        width=WINDOW_RESIZE_EDGE_SIZE,
    ),
    _ResizeHandleSpec(
        ft.WindowResizeEdge.TOP_LEFT,
        ft.MouseCursor.RESIZE_UP_LEFT_DOWN_RIGHT,
        left=0,
        top=0,
        width=WINDOW_RESIZE_CORNER_SIZE,
        height=WINDOW_RESIZE_CORNER_SIZE,
    ),
    _ResizeHandleSpec(
        ft.WindowResizeEdge.TOP_RIGHT,
        ft.MouseCursor.RESIZE_UP_RIGHT_DOWN_LEFT,
        top=0,
        right=0,
        width=WINDOW_RESIZE_CORNER_SIZE,
        height=WINDOW_RESIZE_CORNER_SIZE,
    ),
    _ResizeHandleSpec(
        ft.WindowResizeEdge.BOTTOM_RIGHT,
        ft.MouseCursor.RESIZE_UP_LEFT_DOWN_RIGHT,
        right=0,
        bottom=0,
        width=WINDOW_RESIZE_CORNER_SIZE,
        height=WINDOW_RESIZE_CORNER_SIZE,
    ),
    _ResizeHandleSpec(
        ft.WindowResizeEdge.BOTTOM_LEFT,
        ft.MouseCursor.RESIZE_UP_RIGHT_DOWN_LEFT,
        left=0,
        bottom=0,
        width=WINDOW_RESIZE_CORNER_SIZE,
        height=WINDOW_RESIZE_CORNER_SIZE,
    ),
)


def build_window_resize_handles(page: ft.Page) -> list[ft.GestureDetector]:
    """Build transparent hit areas that start native resizing on frameless windows."""

    handles: list[ft.GestureDetector] = []
    for spec in _RESIZE_HANDLE_SPECS:
        async def start_resizing(
            _event: ft.DragStartEvent,
            edge: ft.WindowResizeEdge = spec.edge,
        ) -> None:
            await page.window.start_resizing(edge)

        handles.append(
            ft.GestureDetector(
                left=spec.left,
                top=spec.top,
                right=spec.right,
                bottom=spec.bottom,
                width=spec.width,
                height=spec.height,
                mouse_cursor=spec.cursor,
                on_pan_start=start_resizing,
                content=ft.Container(expand=True),
            )
        )
    return handles
