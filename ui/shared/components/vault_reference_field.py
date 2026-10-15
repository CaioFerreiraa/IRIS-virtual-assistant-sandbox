from collections.abc import Callable, Iterable

import flet as ft

from util.vault_names import (
    active_vault_query,
    insert_vault_placeholder,
    invalid_vault_references,
)
from ui.theme.colors import (
    PASTEL_DARK_PURPLE,
    PASTEL_GREY_BLUE,
    PASTEL_RED,
    GREY_200,
    SURFACE,
    TEXT_PRIMARY,
)


INVALID_REFERENCE_BACKGROUND = ft.Colors.with_opacity(0.22, PASTEL_RED)


def cursor_offset(field: ft.TextField) -> int | None:
    selection = field.selection
    return selection.extent_offset if selection is not None else None


def matching_vault_names(value: str, available_names: Iterable[str],
                         offset: int | None = None) -> tuple[str, ...]:
    query = active_vault_query(value, offset)
    if query is None:
        return ()
    return tuple(
        name for name in sorted(set(available_names))
        if name.startswith(query)
    )


def sync_reference_field_style(field: ft.TextField,
                               available_names: Iterable[str], *,
                               default_background: str = SURFACE) -> None:
    value = field.value or ""
    names = tuple(available_names)
    query = active_vault_query(value, cursor_offset(field))
    missing = invalid_vault_references(value, names)
    has_unmatched_query = query is not None and not matching_vault_names(
        value, names, cursor_offset(field)
    )
    if field.disabled:
        background = GREY_200
    elif missing or has_unmatched_query:
        background = INVALID_REFERENCE_BACKGROUND
    elif "{{argument}}" in value:
        background = PASTEL_GREY_BLUE
    else:
        background = default_background
    field.bgcolor = background
    field.focused_bgcolor = background


def build_placeholder_text(value: str, *, size: int = 13,
                           color: str = TEXT_PRIMARY) -> ft.Text:
    parts = value.split("{{argument}}")
    spans: list[ft.TextSpan] = []
    for index, part in enumerate(parts):
        if part:
            spans.append(ft.TextSpan(part))
        if index < len(parts) - 1:
            spans.append(
                ft.TextSpan(
                    "{{argument}}",
                    style=ft.TextStyle(
                        bgcolor=PASTEL_GREY_BLUE,
                        color=TEXT_PRIMARY,
                        weight=ft.FontWeight.W_600,
                    ),
                )
            )
    return ft.Text(spans=spans, size=size, color=color)


class VaultReferenceField(ft.Column):
    def __init__(
        self,
        field: ft.TextField,
        available_names: Iterable[str],
        on_change: Callable[[ft.ControlEvent | None], None] | None = None,
    ) -> None:
        self.field = field
        self.available_names = tuple(sorted(set(available_names)))
        self.external_on_change = on_change
        self.suggestions = ft.Row(spacing=6, wrap=True, visible=False)
        self.field.on_change = self._on_change
        super().__init__(
            spacing=5,
            tight=True,
            controls=[self.field, self.suggestions],
        )
        self.refresh()

    def _on_change(self, event: ft.ControlEvent) -> None:
        self.refresh(update=True)
        if self.external_on_change is not None:
            self.external_on_change(event)

    def _select(self, name: str) -> None:
        value, offset = insert_vault_placeholder(
            self.field.value or "",
            name,
            cursor_offset(self.field),
        )
        self.field.value = value
        self.field.selection = ft.TextSelection(offset, offset)
        self.refresh(update=True)
        if self.external_on_change is not None:
            self.external_on_change(None)

    def refresh(self, *, update: bool = False) -> None:
        matches = matching_vault_names(
            self.field.value or "",
            self.available_names,
            cursor_offset(self.field),
        )
        query = active_vault_query(
            self.field.value or "",
            cursor_offset(self.field),
        )
        self.suggestions.controls = [
            ft.Container(
                padding=ft.Padding(left=9, top=5, right=9, bottom=5),
                border_radius=6,
                bgcolor=PASTEL_GREY_BLUE,
                ink=True,
                on_click=lambda _, selected=name: self._select(selected),
                content=ft.Text(
                    f"{{{{vk.{name}}}}}",
                    size=11,
                    color=PASTEL_DARK_PURPLE,
                    weight=ft.FontWeight.W_600,
                ),
            )
            for name in matches
        ]
        self.suggestions.visible = query is not None and bool(matches)
        sync_reference_field_style(self.field, self.available_names)
        if update:
            _update_if_mounted(self.field)
            _update_if_mounted(self.suggestions)


def _update_if_mounted(control: ft.Control) -> None:
    try:
        if control.page is not None:
            control.update()
    except RuntimeError:
        return
