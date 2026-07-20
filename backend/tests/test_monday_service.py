import unittest
from datetime import date
from unittest.mock import patch

from backend.app.services import monday_service


class FakeSheet:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def read_tab_all(self, tab_name):
        return list(self.rows)

    def write_tab(self, tab_name, rows):
        self.rows = list(rows)
        return len(rows)


class MondayTaskPersistenceTests(unittest.TestCase):
    def test_manual_task_is_persisted_in_sheet(self):
        sheet = FakeSheet()
        with patch.object(monday_service, "open_controle", return_value=sheet):
            result = monday_service.add_manual("Telefonar para o aluno")
            loaded = monday_service.load_tasks()

        self.assertEqual(result["manual"][0]["text"], "Telefonar para o aluno")
        self.assertEqual(loaded["manual"][0]["text"], "Telefonar para o aluno")
        self.assertEqual(sheet.rows[0]["Tipo"], "manual")

    def test_new_week_keeps_only_pending_manual_tasks(self):
        current_week = monday_service._monday(date.today()).isoformat()
        sheet = FakeSheet(
            [
                {"Semana": "2000-01-03", "Tipo": "auto", "TarefaId": "queda", "Texto": "", "Concluida": True},
                {"Semana": "2000-01-03", "Tipo": "manual", "TarefaId": "a1", "Texto": "Pendente", "Concluida": False},
                {"Semana": "2000-01-03", "Tipo": "manual", "TarefaId": "a2", "Texto": "Feita", "Concluida": True},
            ]
        )
        with patch.object(monday_service, "open_controle", return_value=sheet):
            result = monday_service.load_tasks()

        self.assertEqual(result["week"], current_week)
        self.assertEqual(result["auto"], {})
        self.assertEqual([item["text"] for item in result["manual"]], ["Pendente"])


if __name__ == "__main__":
    unittest.main()
