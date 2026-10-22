import unittest
from unittest.mock import patch
from backend.app.services import nextfit_roster as roster, presence_service as presence

USERS = [{'id': pid, 'nome': name, 'inativo': False} for pid, name in roster.ACTIVE_PROFESSORS]

class ApiRosterTests(unittest.TestCase):
    def test_exact_seven_users_and_two_distinct_lucas(self):
        self.assertEqual(len(roster.professor_names()), 7)
        self.assertEqual(roster.canonical_professor('Lucas Eduardo Fiore'), 'Lucas Eduardo Fiorio')
        self.assertIsNone(roster.canonical_professor('Lucas'))
        self.assertIsNone(roster.canonical_professor('Lazaro Fernandes'))
        self.assertEqual(roster.canonical_professor('TAIS'), 'Tais Passos')

    def test_assignment_uses_id_not_fuzzy_name_or_legacy(self):
        clients = [{'id': 1, 'nome': 'Aluno teste', 'cliente': {'codigoUsuarioProfessor': 32248190}},
                   {'id': 2, 'nome': 'Outro teste', 'cliente': {'codigoUsuarioProfessor': 28143132}},
                   {'id': 3, 'nome': 'Sem vínculo', 'cliente': {'codigoUsuarioProfessor': 17885209}}]
        contracts = [{'codigoCliente': n, 'status': 'Ativo'} for n in (1, 2, 3)]
        result = roster.build_students(clients, USERS, contracts)
        self.assertEqual([r['Professor'] for r in result], ['Lucas Siqueira', 'Lucas Eduardo Fiorio', ''])
        self.assertEqual([r['Status'] for r in result], ['ATIVO'] * 3)

    def test_missing_or_disabled_official_user_is_not_silently_accepted(self):
        with self.assertRaises(RuntimeError): roster.build_students([], USERS[:-1], [])
        users = [dict(u) for u in USERS]; users[0]['inativo'] = True
        with self.assertRaises(RuntimeError): roster.build_students([], users, [])

    def test_inactive_client_is_not_active_even_with_contract(self):
        rows = roster.build_students([{'id': 1, 'inativo': True}], USERS, [{'codigoCliente': 1, 'status': 'Ativo'}])
        self.assertEqual(rows[0]['Status'], 'INATIVO')

    def test_changed_teacher_revokes_previous_teacher_access(self):
        with patch.object(presence, '_store') as store, patch.object(presence, '_roster_students', return_value=[{'ClienteId': 1, 'Professor': 'Lucas Siqueira'}]):
            store.return_value.client_for_visit.return_value = '1'
            store.return_value.professor_for_visit.return_value = 'Lucas Eduardo Fiorio'
            self.assertFalse(presence._visit_allowed(10, {'role': 'professor', 'name': 'Lucas Eduardo Fiorio'}))
            self.assertTrue(presence._visit_allowed(10, {'role': 'professor', 'name': 'Lucas Siqueira'}))

    def test_api_failure_does_not_authorize_from_stored_owner(self):
        with patch.object(presence, '_store'), patch.object(presence, '_roster_students', side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError): presence._visit_allowed(10, {'role': 'professor', 'name': 'Lucas Siqueira'})

class TeacherLoginTests(unittest.TestCase):
    def test_legacy_alias_uses_current_name_and_excluded_teacher_cannot_login(self):
        from types import SimpleNamespace
        from backend.app.core import security
        settings = SimpleNamespace(admin_password_hash='', admin_password='', professor_password_hashes={},
                                   professor_passwords={'Lucas Eduardo Fiore':'test-one','Lazaro Fernandes':'test-two'})
        with patch.object(security, 'get_settings', return_value=settings):
            self.assertEqual(security.authenticate('test-one')['name'], 'Lucas Eduardo Fiorio')
            self.assertIsNone(security.authenticate('test-two'))

    def test_roster_source_never_uses_legacy_teacher(self):
        from backend.app.services import professor_service
        students = [{'ClienteId':1,'Professor':'Lucas Siqueira','Nome':'Teste'}]
        with patch.object(roster, 'current_roster', return_value={'students':students}), \
             patch.object(professor_service.postgres_data, 'enabled', return_value=True), \
             patch.object(professor_service.cache, 'get_or_set', return_value=[{'ClienteId':1,'Professor':'Antigo','Turno':'MANHÃ'}]):
            current = professor_service._alunos()[0]
        self.assertEqual(current['Professor'], 'Lucas Siqueira')
        self.assertEqual(current['Turno'], 'MANHÃ')
