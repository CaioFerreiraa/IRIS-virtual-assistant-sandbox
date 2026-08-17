from __future__ import annotations

import textwrap

import flet as ft


TOOLTIP_LINE_WIDTH = 52


def build_tooltip_container(content: str) -> ft.Tooltip:
    """Cria o tooltip padrão usando o estilo nativo cinza translúcido do Flet."""
    return ft.Tooltip(
        message=textwrap.fill(
            str(content or "").strip(),
            width=TOOLTIP_LINE_WIDTH,
            break_long_words=False,
            break_on_hyphens=False,
        ),
        padding=12,
        wait_duration=350,
        size_constraints=ft.BoxConstraints(max_width=340),
    )
