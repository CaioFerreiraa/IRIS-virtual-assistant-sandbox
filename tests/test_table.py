import unittest

import flet as ft

from ui.shared.components.table import TableColumn, build_responsive_table


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


if __name__ == "__main__":
    unittest.main()
