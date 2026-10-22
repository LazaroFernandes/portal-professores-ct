from datetime import date
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.professor_analysis import router
from backend.app.core.security import current_user
from backend.app.services import professor_analysis as service


STUDENTS = [
    {"ClienteId": 1, "Nome": "Ana", "Professor": "Atual", "Status": "ATIVO"},
    {"ClienteId": 2, "Nome": "Bruno", "Professor": "Atual", "Status": "ATIVO"},
    {"ClienteId": 3, "Nome": "Caio", "Professor": "Outro", "Status": "ATIVO"},
    {"ClienteId": 4, "Nome": "Dora", "Professor": "", "Status": "ATIVO"},
    {"ClienteId": 5, "Nome": "Inativo", "Professor": "Antigo", "Status": "INATIVO"},
]
RECORDS = [
    {"ClienteId": 1, "Professor": "Antigo", "SemanaInicio": "2026-10-12", "Frequencia": 0, "Desempenho": "Bom", "Relato": "Relato de teste"},
    {"ClienteId": 2, "Professor": "Atual", "SemanaInicio": "2026-10-12", "Frequencia": "  ", "Desempenho": None, "Relato": "Observação"},
    {"ClienteId": 3, "Professor": "Outro", "SemanaInicio": "2026-10-05", "Frequencia": 3, "Desempenho": "Bom", "Relato": "Semana anterior"},
    {"ClienteId": 5, "Professor": "Antigo", "SemanaInicio": "2026-10-12", "Frequencia": 4},
]


class ProfessorAnalysisTests(unittest.TestCase):
    def analyze(self, students=STUDENTS, records=RECORDS, day=date(2026, 10, 15)):
        with patch.object(service, "read_source", return_value=(students, records, "Teste")):
            return service.weekly_analysis(day)

    def test_counts_use_current_active_portfolio_and_zero_is_filled(self):
        data = self.analyze()
        self.assertEqual(data["start"], "2026-10-12")
        self.assertEqual(data["end"], "2026-10-18")
        self.assertEqual(data["available_weeks"], ["2026-10-12", "2026-10-05"])
        summary = data["summary"]
        for key, value in {"total": 4, "complete": 1, "partial": 1, "empty": 2,
                           "pending": 3, "filled": 2, "filled_pct": 50,
                           "complete_pct": 25, "unassigned": 1, "not_opened": 2}.items():
            self.assertEqual(summary[key], value, key)
        ana = data["students"][0]
        self.assertEqual(ana["frequency"], "0")
        self.assertEqual(ana["professor"], "Atual")
        self.assertEqual(ana["record_professor"], "Antigo")
        self.assertEqual(data["quality"]["records_outside_current_portfolio"], 1)
        self.assertEqual(sum(row["total"] for row in data["professors"]), summary["total"])

    def test_previous_week_does_not_reuse_current_records(self):
        data = self.analyze(day=date(2026, 10, 5))
        self.assertEqual(data["summary"]["complete"], 1)
        self.assertEqual(data["students"][0]["status"], "empty")
        self.assertEqual(data["students"][2]["status"], "complete")

    def test_unopened_week_preserves_full_roster(self):
        data = self.analyze(records=[])
        self.assertEqual(data["summary"]["empty"], 4)
        self.assertEqual(data["summary"]["not_opened"], 4)
        self.assertEqual(data["summary"]["filled_pct"], 0)

    def test_empty_roster_has_zero_percentages(self):
        data = self.analyze(students=[], records=[])
        self.assertEqual(data["summary"]["total"], 0)
        self.assertEqual(data["summary"]["filled_pct"], 0)
        self.assertEqual(data["professors"], [])

    def test_duplicates_are_not_double_counted_and_latest_record_wins(self):
        records = [dict(RECORDS[0], AtualizadoEm="2026-10-12 10:00:00"),
                   dict(RECORDS[0], AtualizadoEm="2026-10-13 10:00:00", Relato="Novo relato")]
        data = self.analyze(students=STUDENTS + [STUDENTS[0], {"ClienteId": "inválido"}], records=records)
        self.assertEqual(data["summary"]["total"], 4)
        self.assertEqual(data["students"][0]["report"], "Novo relato")
        self.assertEqual(data["quality"]["duplicate_students"], 1)
        self.assertEqual(data["quality"]["duplicate_records"], 1)
        self.assertEqual(data["quality"]["invalid_students"], 1)

    def test_new_year_normalizes_to_monday(self):
        data = self.analyze(day=date(2027, 1, 1))
        self.assertEqual(data["start"], "2026-12-28")
        self.assertEqual(data["end"], "2027-01-03")

    @patch.object(service.postgres_data, "enabled", return_value=True)
    @patch.object(service.postgres_data, "_table_exists", return_value=True)
    @patch.object(service.postgres_data, "_connect")
    @patch.object(service, "current_roster", return_value={"students": [STUDENTS[0]]})
    def test_postgres_reader_is_read_only_and_never_seeds(self, _roster, connect, _exists, _enabled):
        cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchall.side_effect = [[{"payload": RECORDS[0]}]]
        with patch.object(service.postgres_data, "_ensure_portal_tables") as ensure:
            students, records, source = service.read_source()
        ensure.assert_not_called()
        self.assertEqual(students, [STUDENTS[0]])
        self.assertEqual(records, [RECORDS[0]])
        self.assertEqual(source, "API NextFit + registros PostgreSQL")
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertIn("READ ONLY", statements[0])
        self.assertTrue(all(sql.startswith(("SELECT", "SET TRANSACTION")) for sql in statements))

    @patch.object(service.postgres_data, "enabled", return_value=True)
    @patch.object(service.postgres_data, "_table_exists", return_value=False)
    @patch.object(service.postgres_data, "_connect", return_value=MagicMock())
    @patch.object(service, "current_roster", return_value={"students": STUDENTS})
    def test_missing_postgres_tables_are_not_reported_as_zero(self, *_):
        with self.assertRaises(RuntimeError):
            service.read_source()

    @patch.object(service.postgres_data, "enabled", return_value=False)
    @patch.object(service, "open_controle")
    @patch.object(service, "current_roster", return_value={"students": STUDENTS})
    def test_sheets_source_is_read_only(self, _roster, open_sheet, _enabled):
        open_sheet.return_value.read_tab_all.side_effect = [RECORDS]
        students, records, source = service.read_source()
        self.assertEqual((students, records, source), (STUDENTS, RECORDS, "API NextFit + registros Google Sheets"))
        self.assertEqual([call[0] for call in open_sheet.return_value.mock_calls], ["read_tab_all"])


class AnalysisAccessTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        self.client = TestClient(self.app)

    def test_anonymous_request_is_rejected(self):
        self.assertEqual(self.client.get("/api/admin/professors/analysis").status_code, 401)

    @patch.object(service, "read_source")
    def test_professor_cannot_read_other_portfolios(self, source):
        self.app.dependency_overrides[current_user] = lambda: {"role": "professor", "name": "Atual"}
        self.assertEqual(self.client.get("/api/admin/professors/analysis").status_code, 403)
        source.assert_not_called()

    @patch.object(service, "read_source", return_value=(STUDENTS, RECORDS, "Teste"))
    def test_admin_gets_analysis_and_invalid_date_is_rejected(self, _source):
        self.app.dependency_overrides[current_user] = lambda: {"role": "admin"}
        response = self.client.get("/api/admin/professors/analysis?start=2026-10-15")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["total"], 4)
        self.assertEqual(self.client.get("/api/admin/professors/analysis?start=invalid").status_code, 422)

    @patch.object(service, "read_source", side_effect=RuntimeError("private database failure"))
    def test_source_error_is_not_presented_as_empty_data(self, _source):
        self.app.dependency_overrides[current_user] = lambda: {"role": "admin"}
        response = self.client.get("/api/admin/professors/analysis")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private database", response.text)
