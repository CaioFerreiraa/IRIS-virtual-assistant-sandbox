from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import flet as ft

from ui.theme.colors import (
    BORDER,
    PRIMARY_SOFT,
    SURFACE,
    BLUE_GREY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


@dataclass(frozen=True)
class TableColumn:
    key: str
    label: str
    width: int


TableRow = Mapping[str, object]


def build_responsive_table(
    columns: Sequence[TableColumn],
    rows: Sequence[TableRow],
    empty_message: str = "Nenhum registro encontrado.",
) -> ft.Container:
    table_width = sum(column.width for column in columns)

    return ft.Container(
        expand=True,
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=8,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Row(
            expand=True,
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Column(
                    width=table_width,
                    expand=True,
                    spacing=0,
                    controls=[
                        _build_header(columns),
                        _build_body(columns, rows, empty_message),
                    ],
                ),
            ],
        ),
    )


def _build_header(columns: Sequence[TableColumn]) -> ft.Container:
    return ft.Container(
        height=46,
        bgcolor=PRIMARY_SOFT,
        border=ft.Border.only(bottom=ft.BorderSide(1, BORDER)),
        content=ft.Row(
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                _build_cell(
                    column.width,
                    ft.Text(
                        column.label,
                        size=12,
                        weight=ft.FontWeight.W_700,
                        color=TEXT_PRIMARY,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        no_wrap=True,
                    ),
                    is_header=True,
                )
                for column in columns
            ],
        ),
    )


def _build_body(
    columns: Sequence[TableColumn],
    rows: Sequence[TableRow],
    empty_message: str,
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
            _build_row(columns, row, row_index)
            for row_index, row in enumerate(rows)
        ],
    )


def _build_row(
    columns: Sequence[TableColumn],
    row: TableRow,
    row_index: int,
) -> ft.Container:
    return ft.Container(
        height=54,
        bgcolor=BLUE_GREY if row_index % 2 else SURFACE,
        border=ft.Border.only(bottom=ft.BorderSide(1, BORDER)),
        content=ft.Row(
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                _build_cell(column.width, _normalize_cell_value(row.get(column.key)))
                for column in columns
            ],
        ),
    )


def _build_cell(
    width: int,
    content: ft.Control,
    is_header: bool = False,
) -> ft.Container:
    return ft.Container(
        width=width,
        height=46 if is_header else 54,
        padding=ft.Padding(left=14, top=0, right=14, bottom=0),
        alignment=ft.Alignment.CENTER_LEFT,
        border=ft.Border.only(right=ft.BorderSide(1, BORDER)),
        content=content,
    )


def _normalize_cell_value(value: object) -> ft.Control:
    if isinstance(value, ft.Control):
        return value

    text = "" if value is None else str(value)
    return ft.Text(
        text,
        size=13,
        color=TEXT_PRIMARY,
        overflow=ft.TextOverflow.ELLIPSIS,
        no_wrap=True,
        tooltip=text,
    )
