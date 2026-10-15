from dataclasses import dataclass
from typing import Sequence, Mapping

import flet as ft

from ui.theme.colors import (
    BORDER,
    PASTEL_PURPLE,
    SURFACE,
    BLUE_GREY,
    TEXT_PRIMARY,
    TEXT_SECONDARY, PASTEL_DARK_PURPLE,
)


@dataclass(frozen=True)
class TableColumn:
    key: str
    label: str
    weight: int = 1


TableRow = Mapping[str, object]


def build_responsive_table(
    columns: Sequence[TableColumn],
    rows: Sequence[TableRow],
    empty_message: str = "Nenhum registro encontrado.",
    *,
    row_height: int = 54,
) -> ft.Container:
    return ft.Container(
        expand=True,
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=8,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Column(
            expand=True,
            spacing=0,
            controls=[
                _build_header(columns),
                _build_body(columns, rows, empty_message, row_height),
            ],
        ),
    )


def _build_header(columns: Sequence[TableColumn]) -> ft.Container:
    return ft.Container(
        height=40,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1.0, -1.0),
            end=ft.Alignment(1.0, 1.0),
            colors=[
                '#b08fd9',
                ft.Colors.with_opacity(0.85, PASTEL_PURPLE),
                ft.Colors.with_opacity(0.65, PASTEL_PURPLE),
                ft.Colors.with_opacity(0.45, PASTEL_PURPLE),
            ],
        ),
        border=ft.Border.only(bottom=ft.BorderSide(1, BORDER)),
        content=ft.Row(
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                _build_cell(
                    column.weight,
                    ft.Text(
                        column.label,
                        size=12,
                        weight=ft.FontWeight.W_700,
                        color=TEXT_PRIMARY,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        no_wrap=True,
                    ),
                    is_header=True,
                    tooltip=column.label if column.key != "actions" else None,
                )
                for column in columns
            ],
        ),
    )


def _build_body(
    columns: Sequence[TableColumn],
    rows: Sequence[TableRow],
    empty_message: str,
    row_height: int,
) -> ft.Control:
    if not rows:
        return ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Text(
                empty_message,
                size=14,
                color=TEXT_SECONDARY,
            ),
        )

    return ft.ListView(
        expand=True,
        spacing=0,
        padding=0,
        auto_scroll=False,
        controls=[
            _build_row(columns, row, row_index, row_height)
            for row_index, row in enumerate(rows)
        ],
    )


def _build_row(
    columns: Sequence[TableColumn],
    row: TableRow,
    row_index: int,
    row_height: int,
) -> ft.Container:
    return ft.Container(
        height=row_height,
        bgcolor=BLUE_GREY if row_index % 2 else SURFACE,
        border=ft.Border.only(bottom=ft.BorderSide(1, BORDER)),
        content=ft.Row(
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                _build_data_cell(column, row.get(column.key), row_height)
                for column in columns
            ],
        ),
    )


def _build_cell(
    weight: int,
    content: ft.Control,
    is_header: bool = False,
    height: int = 52,
    tooltip: str | None = None,
) -> ft.Container:
    return ft.Container(
        expand=weight,
        height=40 if is_header else height,
        padding=ft.Padding(left=14, top=0, right=14, bottom=0),
        alignment=ft.Alignment.CENTER_LEFT,
        border=ft.Border.only(right=ft.BorderSide(1, BORDER)),
        tooltip=tooltip,
        content=content,
    )


def _build_data_cell(column: TableColumn, value: object, height: int) -> ft.Container:
    is_action = column.key == "actions"
    content = _normalize_cell_value(value, selectable=not is_action)
    tooltip = _cell_text(value) if not is_action else ""
    return _build_cell(
        column.weight,
        content,
        height=height,
        tooltip=(tooltip or "Vazio") if not is_action else None,
    )


def _normalize_cell_value(value: object, *, selectable: bool) -> ft.Control:
    if isinstance(value, ft.Control):
        if selectable:
            _prepare_text_controls(value)
        return value

    text = "" if value is None else str(value)
    control = ft.Text(
        text,
        size=13,
        color=TEXT_PRIMARY,
        overflow=ft.TextOverflow.ELLIPSIS,
        no_wrap=True,
        tooltip=text,
    )
    if selectable:
        _prepare_text_controls(control)
    return control


def _prepare_text_controls(control: ft.Control) -> None:
    if isinstance(control, ft.Text):
        control.selectable = True
        control.show_selection_cursor = True
        control.on_tap = _copy_text(control.value)
        return
    child = getattr(control, "content", None)
    if isinstance(child, ft.Control):
        _prepare_text_controls(child)
    for child in getattr(control, "controls", ()) or ():
        if isinstance(child, ft.Control):
            _prepare_text_controls(child)


def _copy_text(value: str):
    async def on_tap(event: ft.ControlEvent) -> None:
        page = getattr(event, "page", None)
        if page is not None and value:
            clipboard = next(
                (service for service in page.services if isinstance(service, ft.Clipboard)),
                None,
            )
            if clipboard is None:
                clipboard = ft.Clipboard()
                page.services.append(clipboard)
                page.update()
            await clipboard.set(value)
    return on_tap


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, ft.Text):
        return value.value or ""
    if isinstance(value, ft.Control):
        parts = []
        child = getattr(value, "content", None)
        if isinstance(child, ft.Control):
            parts.append(_cell_text(child))
        parts.extend(
            _cell_text(child)
            for child in getattr(value, "controls", ()) or ()
            if isinstance(child, ft.Control)
        )
        return " ".join(part for part in parts if part)
    return str(value)
