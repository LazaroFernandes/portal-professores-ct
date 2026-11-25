import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.professor import router
from backend.app.core.security import current_user
from backend.app.services import professor_service


PATH = "/api/professor/students"
STUDENTS = [
    {"ClienteId": 1, "Nome": "Zeta", "Professor": "Prof A", "Status": "ATIVO", "Turno": ""},
    {"ClienteId": 2, "Nome": "Alfa", "Professor": "Prof A", "Status": "ATIVO", "Turno": "MANHÃ",
     "Plano": "Plano A", "Modalidade": "Modalidade A"},
    {"ClienteId": 3, "Nome": "Inativo", "Professor": "Prof A", "Status": "INATIVO"},
    {"ClienteId": 4, "Nome": "Beta", "Professor": "Prof B", "Status": "ATIVO", "Turno": "NOITE"},
]


class ProfessorStudentsTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        students = patch.object(professor_service, "_alunos", return_value=STUDENTS)
        self.students = students.start()
        self.addCleanup(students.stop)
        names = patch.object(professor_service, "professores_disponiveis", return_value=["Prof A", "Prof B"])
        names.start()
        self.addCleanup(names.stop)

    def login(self, role, name):
        self.app.dependency_overrides[current_user] = lambda: {"role": role, "name": name}

    def test_anonymous_and_unrecognized_roles_cannot_read(self):
        self.assertEqual(self.client.get(PATH).status_code, 401)
        self.login("visitante", "Teste")
        self.assertEqual(self.client.get(PATH).status_code, 403)
        self.students.assert_not_called()

    def test_teacher_only_gets_own_active_students_sorted(self):
        self.login("professor", "Prof A")
        response = self.client.get(PATH, params={"professor": "Prof B"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["professors"], ["Prof A"])
        self.assertEqual([row["client_id"] for row in payload["students"]], [2, 1])
        self.assertEqual(payload["students"][0]["plan"], "Plano A")
        self.assertEqual(payload["students"][0]["modality"], "Modalidade A")
        self.assertEqual(payload["summary"], {"total": 2, "morning": 1, "afternoon": 0, "evening": 0, "unassigned": 1})

    def test_admin_can_select_a_portfolio_and_refresh_it(self):
        self.login("admin", "Gestão")
        response = self.client.get(PATH, params={"professor": "Prof B", "refresh": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["professors"], ["Prof A", "Prof B"])
        self.assertEqual([row["client_id"] for row in response.json()["students"]], [4])
        self.students.assert_called_once_with(refresh=True)
        self.assertEqual(self.client.get(PATH, params={"professor": "Desconhecido"}).status_code, 400)

    def test_empty_and_unavailable_portfolios_are_distinct(self):
        self.login("professor", "Sem alunos")
        response = self.client.get(PATH)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 0)
        self.students.side_effect = RuntimeError("indisponível")
        self.assertEqual(self.client.get(PATH).status_code, 503)
