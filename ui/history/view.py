import unicodedata

import flet as ft

from database.db import SessionLocal
from database.models import Log
from repositories.log_repository import LogRepository
from repositories.module_repository import ModuleRepository
from ui.shared.components.route_content_container import build_route_content_container
from ui.shared.components.table import TableColumn, build_responsive_table
from ui.theme.colors import (
    CANCEL,
    CONFIRM,
    PRIMARY_SOFT,
    TEXT_PRIMARY,
    WARNING,
    BORDER,
    PASTEL_DARK_PURPLE,
    PASTEL_PURPLE,
    SURFACE,
    TEXT_SECONDARY, BLUE_GREY,
)


HISTORY_COLUMNS = (
    TableColumn("id", "ID", 1),
    TableColumn("created_at", "Data", 2),
    TableColumn("module", "Módulo", 3),
    TableColumn("routine", "Rotina", 2),
    TableColumn("status", "Status", 2),
    TableColumn("message", "Mensagem", 5),
)


def build_history_view() -> ft.Container:
    return HistoryViewState().build()


class HistoryViewState:
    def __init__(self):
        self.rows = _load_history_rows()
        self.filtered_rows = list(self.rows)
        self.subtitle_text = ft.Text(
            self._build_subtitle(),
            size=13,
            color=TEXT_SECONDARY,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.search_input = ft.TextField(
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            hint_text="Pesquisar no histórico...",
            text_style=ft.TextStyle(size=14, color=TEXT_PRIMARY),
            hint_style=ft.TextStyle(size=14, color=TEXT_SECONDARY),
            border_color=BORDER,
            focused_border_color=BLUE_GREY,
            cursor_color=PASTEL_DARK_PURPLE,
            border_radius=8,
            dense=True,
            expand=True,
            on_change=self.on_search_change,
        )
        self.table_container = ft.Container(expand=True)

    def build(self) -> ft.Container:
        self._render_table()

        return build_route_content_container(
            content=ft.Column(
                expand=True,
                spacing=12,
                controls=[
                    self._build_search_bar(),
                    self.table_container,
                ],
            ),
            icon=ft.Icons.HISTORY_ROUNDED,
            title="Histórico",
            subtitle=self.subtitle_text,
        )

    def _build_search_bar(self) -> ft.Container:
        return ft.Container(
            bgcolor=SURFACE,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            padding=ft.Padding(left=10, top=8, right=10, bottom=8),
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    self.search_input,
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        icon_color=TEXT_SECONDARY,
                        tooltip="Limpar pesquisa",
                        on_click=self.clear_search,
                    ),
                ],
            ),
        )

    def on_search_change(self, event: ft.ControlEvent) -> None:
        self._filter_rows(event.control.value or "")
        self._render_table()
        self._update_if_mounted(self.subtitle_text)
        self._update_if_mounted(self.table_container)

    def clear_search(self, event: ft.ControlEvent) -> None:
        self.search_input.value = ""
        self._filter_rows("")
        self._render_table()
        self._update_if_mounted(self.search_input)
        self._update_if_mounted(self.subtitle_text)
        self._update_if_mounted(self.table_container)

    def _filter_rows(self, query: str) -> None:
        normalized_query = _normalize_search_text(query)
        tokens = normalized_query.split()
        if not tokens:
            self.filtered_rows = list(self.rows)
            self.subtitle_text.value = self._build_subtitle()
            return

        self.filtered_rows = [
            row
            for row in self.rows
            if all(token in str(row.get("_search_text", "")) for token in tokens)
        ]
        self.subtitle_text.value = self._build_subtitle(query)

    def _render_table(self) -> None:
        self.table_container.content = build_responsive_table(
            columns=HISTORY_COLUMNS,
            rows=self.filtered_rows,
            empty_message="Nenhuma execução encontrada.",
        )

    def _build_subtitle(self, query: str = "") -> str:
        if query.strip():
            return f"{len(self.filtered_rows)} de {len(self.rows)} registros encontrados"
        return f"{len(self.rows)} registros encontrados"

    def _update_if_mounted(self, control: ft.Control) -> None:
        try:
            if control.page is not None:
                control.update()
        except RuntimeError:
            return


def load_history_rows(
    *,
    module_id: int | None = None,
    session_factory=SessionLocal,
) -> list[dict[str, object]]:
    db = session_factory()
    try:
        module_repository = ModuleRepository(db)
        logs = LogRepository(db).list_logs(module_id=module_id)
        return [
            _build_history_row(log, module_repository)
            for log in logs
        ]
    finally:
        db.close()


def _load_history_rows() -> list[dict[str, object]]:
    return load_history_rows()


def _build_history_row(log: Log, module_repository: ModuleRepository) -> dict[str, object]:
    created_at = _format_datetime(log.created_at)
    module_path = module_repository.get_module_path(log.module) if log.module else "-"
    routine_name = log.routine.name if log.routine else "-"
    status_label = _status_label(log.status)
    message = log.message or "-"

    return {
        "id": log.id,
        "created_at": created_at,
        "module": module_path,
        "routine": routine_name,
        "status": _build_status_chip(log.status),
        "message": message,
        "_search_text": _normalize_search_text(
            f"{log.id} {created_at} {module_path} {routine_name} {status_label} {message}"
        ),
    }


def _status_label(status: str) -> str:
    normalized_status = (status or "").strip().lower()
    return {
        "success": "Sucesso",
        "error": "Erro",
        "failed": "Erro",
        "failure": "Erro",
    }.get(normalized_status, status or "-")


def _build_status_chip(status: str) -> ft.Container:
    normalized_status = (status or "").strip().lower()
    label = _status_label(status)
    color = {
        "success": CONFIRM,
        "error": CANCEL,
        "failed": CANCEL,
        "failure": CANCEL,
        "warning": WARNING,
    }.get(normalized_status, PRIMARY_SOFT)

    return ft.Container(
        height=28,
        padding=ft.Padding(left=10, top=0, right=10, bottom=0),
        border_radius=8,
        alignment=ft.Alignment.CENTER,
        bgcolor=color,
        content=ft.Text(
            label,
            size=12,
            weight=ft.FontWeight.W_700,
            color=TEXT_PRIMARY,
            overflow=ft.TextOverflow.ELLIPSIS,
            no_wrap=True,
            tooltip=label,
        ),
    )


def _format_datetime(value) -> str:
    if value is None:
        return "-"

    return value.strftime("%d/%m/%Y %H:%M:%S")


def _normalize_search_text(value: str) -> str:
    normalized_value = unicodedata.normalize("NFD", value.lower())
    chars: list[str] = []
    for char in normalized_value:
        if unicodedata.category(char) == "Mn":
            continue
        if char.isalnum() or char.isspace():
            chars.append(char)
            continue
        if char not in "-_":
            chars.append(" ")

    return " ".join("".join(chars).split())
