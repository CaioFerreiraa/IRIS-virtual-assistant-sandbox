import unittest
from unittest.mock import patch

from ui.history import view


class HistoryViewTests(unittest.TestCase):
    def test_filter_matches_text_without_accents_or_case(self) -> None:
        rows = [
            {
                "id": 1,
                "created_at": "16/08/2026 10:00:00",
                "module": "Módulo > E-mail",
                "routine": "-",
                "status": "Sucesso",
                "message": "Mensagem enviada",
                "_search_text": view._normalize_search_text(
                    "1 16/08/2026 10:00:00 Módulo > E-mail - Sucesso Mensagem enviada"
                ),
            },
            {
                "id": 2,
                "created_at": "16/08/2026 11:00:00",
                "module": "Arquivos",
                "routine": "Backup",
                "status": "Erro",
                "message": "Falha ao abrir pasta",
                "_search_text": view._normalize_search_text(
                    "2 16/08/2026 11:00:00 Arquivos Backup Erro Falha ao abrir pasta"
                ),
            },
        ]

        with patch.object(view, "_load_history_rows", return_value=rows):
            state = view.HistoryViewState()

        state._filter_rows("modulo email sucesso")

        self.assertEqual([rows[0]], state.filtered_rows)
        self.assertEqual("1 de 2 registros encontrados", state.subtitle_text.value)

    def test_empty_filter_restores_all_rows(self) -> None:
        rows = [
            {"id": 1, "_search_text": "sucesso"},
            {"id": 2, "_search_text": "erro"},
        ]

        with patch.object(view, "_load_history_rows", return_value=rows):
            state = view.HistoryViewState()

        state._filter_rows("erro")
        state._filter_rows("")

        self.assertEqual(rows, state.filtered_rows)
        self.assertEqual("2 registros encontrados", state.subtitle_text.value)


if __name__ == "__main__":
    unittest.main()
