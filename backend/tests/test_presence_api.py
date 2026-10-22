from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app.api.presence import router
from backend.app.core.security import current_user, require_csrf
from backend.app.services import presence_service as service


class PresenceAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = service.PresenceStore(Path(self.temp.name) / 'test.db')
        self.now = datetime.now(service.TIMEZONE)
        self.store.ingest([{'CodigoCliente': n, 'NomeCliente': f'Aluno teste {n}',
                           'Data': self.now.isoformat(), 'DescricaoTipo': 'Acesso'} for n in (1, 2)])
        for row in self.store.active(self.now):
            self.store.set_student_context(row['id'], f'Professor {row["client_id"]}', '')
        self.app = FastAPI()
        self.app.include_router(router)
        self.client = TestClient(self.app)
        self.patches = [patch.object(service, '_roster_students', return_value=[{'ClienteId': n, 'Professor': f'Professor {n}'} for n in (1, 2)]), patch.object(service, '_store', return_value=self.store),
                        patch.object(service, 'refresh_if_due'), patch.object(service, 'refresh_training_if_due')]
        for item in self.patches: item.start()

    def tearDown(self):
        for item in reversed(self.patches): item.stop()
        self.temp.cleanup()

    def test_anonymous_is_denied(self):
        self.assertEqual(self.client.get('/api/presence').status_code, 401)

    def test_professor_sees_only_own_students_and_cannot_read_other_training(self):
        self.app.dependency_overrides[current_user] = lambda: {'role': 'professor', 'name': 'Professor 1'}
        data = self.client.get('/api/presence').json()
        self.assertEqual([s['client_id'] for s in data['students']], ['1'])
        other = next(s for s in self.store.active(self.now) if s['client_id'] == '2')
        self.assertEqual(self.client.get(f'/api/presence/{other["id"]}/training').status_code, 403)

    def test_csrf_required_and_cross_professor_write_denied(self):
        user = {'role': 'professor', 'name': 'Professor 1', 'csrf': 'test'}
        self.app.dependency_overrides[current_user] = lambda: user
        other = next(s for s in self.store.active(self.now) if s['client_id'] == '2')
        url = f'/api/presence/{other["id"]}/attendance'
        self.assertEqual(self.client.put(url, json={'desempenho': 'Bom'}).status_code, 403)
        self.app.dependency_overrides[require_csrf] = lambda: user
        self.assertEqual(self.client.put(url, json={'desempenho': 'Bom'}).status_code, 404)
        self.assertTrue(all(not s['attendance_finalized_at'] for s in self.store.active(self.now)))

    def test_own_attendance_is_saved_and_reopened(self):
        self.app.dependency_overrides[require_csrf] = lambda: {'role': 'professor', 'name': 'Professor 1'}
        own = next(s for s in self.store.active(self.now) if s['client_id'] == '1')
        result = self.client.put(f'/api/presence/{own["id"]}/attendance', json={'desempenho': 'Bom', 'observacao': 'Teste'})
        self.assertEqual(result.status_code, 200)
        reopened = service.PresenceStore(self.store.path)
        record = next(s for s in reopened.active(self.now, include_finished=True) if s['client_id'] == '1')
        self.assertEqual(record['observation'], 'Teste')
        self.assertEqual(record['status'], 'ATENDIMENTO FINALIZADO')
