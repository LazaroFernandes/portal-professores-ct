from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.app.services import professor_service


ALUNOS = [
    {"ClienteId": 1, "Nome": "Aluno A", "Professor": "Prof A", "Status": "ATIVO", "Turno": "MANHÃ"},
    {"ClienteId": 2, "Nome": "Aluno B", "Professor": "Prof B", "Status": "ATIVO", "Turno": "NOITE"},
]
REGISTROS = [
    {"ClienteId": 1, "Nome": "Aluno A", "Professor": "Prof A", "SemanaInicio": "2026-07-20", "Frequencia": 0, "Desempenho": "", "Relato": ""},
]


class ProfessorServiceTests(unittest.TestCase):
    @patch.object(professor_service, "_registros", return_value=REGISTROS)
    @patch.object(professor_service, "_alunos", return_value=ALUNOS)
    def test_zero_frequency_counts_as_completed(self, _alunos, _registros) -> None:
        payload = professor_service.week_payload(
            {"role": "professor", "name": "Prof A"}, None, "2026-07-20"
        )
        self.assertEqual(payload["summary"]["completed"], 1)
        self.assertEqual(payload["students"][0]["frequency"], "0")

    @patch.object(professor_service, "_alunos", return_value=ALUNOS)
    def test_professor_cannot_select_another_portfolio(self, _alunos) -> None:
        selected = professor_service.resolve_professor(
            {"role": "professor", "name": "Prof A"}, "Prof B"
        )
        self.assertEqual(selected, "Prof A")


if __name__ == "__main__":
    unittest.main()
