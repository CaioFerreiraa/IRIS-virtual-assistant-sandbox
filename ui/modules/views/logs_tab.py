from __future__ import annotations

import flet as ft

from ui.history.view import HISTORY_COLUMNS, load_history_rows
from ui.shared.components.table import build_responsive_table


class ModuleLogsTabMixin:
    def _build_log_tab(self) -> ft.Container:
        self._refresh_logs()
        return self.log_container

    def _refresh_logs(self) -> None:
        if not bool(self.detail["is_executable"]):
            return
        rows = load_history_rows(
            module_id=int(self.detail["id"]),
            session_factory=self.session_factory,
        )
        self.log_container.content = build_responsive_table(
            columns=HISTORY_COLUMNS,
            rows=rows,
            empty_message="Este módulo ainda não possui registros de execução.",
        )
        self._update_if_mounted(self.log_container)
