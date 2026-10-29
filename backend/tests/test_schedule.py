from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api import schedule
from backend.app.core.security import current_user
from backend.app.services.presence_service import PresenceStore


def test_schedule_admin_persistence_and_validation(tmp_path, monkeypatch):
    store = PresenceStore(tmp_path / 'schedule.db')
    monkeypatch.setattr(schedule, '_store', lambda: store)
    app.dependency_overrides[current_user] = lambda: {'role': 'admin', 'csrf': 'token'}
    client = TestClient(app)
    teacher = {'id': 'test:1', 'name': 'Teste', 'source': 'test', 'rate': 25, 'shifts': [{'day': 0, 'start': '08:00', 'end': '12:30'}]}
    try:
        assert client.put('/api/admin/schedule', json={'teachers': [teacher]}).status_code == 403
        assert client.put('/api/admin/schedule', json={'teachers': [teacher]}, headers={'X-CSRF-Token': 'token'}).status_code == 200
        assert client.get('/api/admin/schedule').json()['teachers'][0]['name'] == 'Teste'
        teacher['shifts'][0]['end'] = '07:00'
        assert client.put('/api/admin/schedule', json={'teachers': [teacher]}, headers={'X-CSRF-Token': 'token'}).status_code == 422
        app.dependency_overrides[current_user] = lambda: {'role': 'professor', 'csrf': 'token'}
        assert client.get('/api/admin/schedule').status_code == 403
        assert client.put('/api/admin/schedule', json={'teachers': []}, headers={'X-CSRF-Token': 'token'}).status_code == 403
        assert client.get('/api/admin/schedule/users').status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_nextfit_users_only_active(monkeypatch):
    class Client:
        def __init__(self, *args): pass
        def usuarios(self): return [{'id': 1, 'nome': 'Ativo'}, {'id': 2, 'nome': 'Inativo', 'inativo': True}]
    monkeypatch.setenv('NEXTFIT_API_KEY', 'test')
    monkeypatch.setenv('NEXTFIT_BASE_URL', 'https://example.test')
    monkeypatch.setattr(schedule, 'NextFitClient', Client)
    app.dependency_overrides[current_user] = lambda: {'role': 'admin'}
    try:
        result = TestClient(app).get('/api/admin/schedule/users')
        assert result.status_code == 200
        assert result.json() == {'users': [{'id': '1', 'name': 'Ativo'}]}
    finally:
        app.dependency_overrides.clear()
