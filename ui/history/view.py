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
)


HISTORY_COLUMNS = (
    TableColumn("id", "ID", 70),
    TableColumn("created_at", "Data", 160),
    TableColumn("module", "Módulo", 280),
    TableColumn("routine", "Rotina", 180),
    TableColumn("status", "Status", 130),
    TableColumn("message", "Mensagem", 500),
)


def build_history_view() -> ft.Container:
    rows = _load_history_rows()

    return build_route_content_container(
        content=build_responsive_table(
            columns=HISTORY_COLUMNS,
            rows=rows,
            empty_message="Nenhuma execução registrada.",
        ),
        icon=ft.Icons.HISTORY_ROUNDED,
        title="Histórico",
        subtitle=f"{len(rows)} registros encontrados",
    )


def _load_history_rows() -> list[dict[str, object]]:
    db = SessionLocal()
    try:
        module_repository = ModuleRepository(db)
        logs = LogRepository(db).list_logs()
        return [
            _build_history_row(log, module_repository)
            for log in logs
        ]
    finally:
        db.close()


def _build_history_row(log: Log, module_repository: ModuleRepository) -> dict[str, object]:
    return {
        "id": log.id,
        "created_at": _format_datetime(log.created_at),
        "module": module_repository.get_module_path(log.module) if log.module else "-",
        "routine": log.routine.name if log.routine else "-",
        "status": _build_status_chip(log.status),
        "message": log.message or "-",
    }


def _build_status_chip(status: str) -> ft.Container:
    normalized_status = (status or "").strip().lower()
    label = {
        "success": "Sucesso",
        "error": "Erro",
        "failed": "Erro",
        "failure": "Erro",
    }.get(normalized_status, status or "-")
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
