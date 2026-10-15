import unittest
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import flet as ft

from ui.shared.components.table import TableColumn, build_responsive_table
from ui.theme.colors import PASTEL_PURPLE


class ResponsiveTableTests(unittest.TestCase):
    def test_columns_use_weighted_expand_to_fill_available_width(self) -> None:
        table = build_responsive_table(
            columns=(
                TableColumn("id", "ID", 1),
                TableColumn("message", "Mensagem", 4),
            ),
            rows=(
                {"id": 1, "message": "Executado com sucesso."},
            ),
        )

        content_column = table.content
        self.assertIsInstance(content_column, ft.Column)
        header = content_column.controls[0]
        body = content_column.controls[1]
        first_row = body.controls[0]

        header_cells = header.content.controls
        row_cells = first_row.content.controls

        self.assertEqual([1, 4], [cell.expand for cell in header_cells])
        self.assertEqual([1, 4], [cell.expand for cell in row_cells])
        self.assertIsNone(header_cells[0].width)
        self.assertIsNone(row_cells[0].width)

    def test_text_cells_have_tooltips_selection_and_click_to_copy(self) -> None:
        table = build_responsive_table(
            columns=(
                TableColumn("name", "Nome"),
                TableColumn("count", "Quantidade"),
                TableColumn("actions", "Ações"),
            ),
            rows=({"name": ft.Text("Texto longo"), "count": 12,
                   "actions": ft.IconButton(ft.Icons.EDIT_OUTLINED)},),
        )
        header, body = table.content.controls
        self.assertEqual(PASTEL_PURPLE, header.bgcolor)
        name_cell, count_cell, action_cell = body.controls[0].content.controls
        self.assertEqual("Texto longo", name_cell.tooltip)
        self.assertEqual("12", count_cell.tooltip)
        self.assertIsNone(action_cell.tooltip)
        self.assertTrue(name_cell.content.selectable)
        self.assertTrue(count_cell.content.show_selection_cursor)

        clipboard = ft.Clipboard()
        clipboard.set = AsyncMock()
        page = SimpleNamespace(services=[clipboard], update=Mock())
        asyncio.run(name_cell.content.on_tap(SimpleNamespace(page=page)))
        clipboard.set.assert_awaited_once_with("Texto longo")


if __name__ == "__main__":
    unittest.main()
