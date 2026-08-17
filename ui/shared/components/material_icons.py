import flet as ft

from ui.theme.fonts import MATERIAL_SYMBOLS_FONT


DEFAULT_MATERIAL_ICON = "extension"


def material_icon(
    name: str,
    size: int = 24,
    color: str | None = None,
    weight: ft.FontWeight | None = None,
) -> ft.Text:
    """Renderiza uma ligature da fonte local Material Symbols Rounded."""
    return ft.Text(
        value=(name or DEFAULT_MATERIAL_ICON).strip() or DEFAULT_MATERIAL_ICON,
        font_family=MATERIAL_SYMBOLS_FONT,
        size=size,
        color=color,
        selectable=False,
        no_wrap=True,
        weight=weight or ft.FontWeight.NORMAL,
        style=ft.TextStyle(),
    )
