from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app.api.daily import router
from backend.app.api.professor import router as weekly_router
from backend.app.core.security import current_user
from backend.app.services import daily_workflow as daily, presence_service as presence


class DailyWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=presence.PresenceStore(Path(self.temp.name)/'daily.sqlite')
        self.teacher={'role':'professor','name':daily.professor_names()[0],'csrf':'test'}
        self.admin={'role':'admin','name':'Administrador','csrf':'test'};self.user=self.teacher
        self.assignments=[{'ClienteId':'1','Professor':self.teacher['name']},{'ClienteId':'2','Professor':daily.professor_names()[1]}]
        self.patches=[patch.object(presence,'_store',return_value=self.store),patch.object(presence,'_roster_students',side_effect=lambda:self.assignments),patch.object(presence,'refresh_if_due')]
        for p in self.patches:p.start()
        stamp=daily.now()
        self.store.ingest([{'CodigoCliente':i,'NomeCliente':f'Aluno fictício {i}','Data':stamp.isoformat(),'DescricaoTipo':'Acesso'} for i in (1,2)])
        self.rows=self.store.active(stamp,include_finished=True);self.own=next(r['id'] for r in self.rows if r['client_id']=='1');self.other=next(r['id'] for r in self.rows if r['client_id']=='2')
        self.app=FastAPI();self.app.include_router(router);self.app.include_router(weekly_router)
        self.app.dependency_overrides[current_user]=lambda:self.user
        self.client=TestClient(self.app);self.headers={'X-CSRF-Token':'test'}
        self.body={'contact':'accompanied','outcome':'completed','pain':'no','follow_up':False,'note':'','version':0}

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def save(self,body=None,visit=None):return self.client.put(f'/api/daily/records/{visit or self.own}',json=body or self.body,headers=self.headers)
    def get_action(self):return self.client.get('/api/daily/actions').json()['actions'][0]
    def action_body(self,a,**changes):
        body={k:a[k] for k in ('version','status','assigned_to','priority','instruction','result')};body['due_date']=a['due_date'] or None;return {**body,**changes}
    def update(self,a,**changes):return self.client.put(f'/api/daily/actions/{a["id"]}',json=self.action_body(a,**changes),headers=self.headers)
    def adverse(self):return self.save({**self.body,'pain':'yes','note':'Relato fictício que precisa de retorno.'})

    def test_auth_csrf_and_carteira_isolation(self):
        self.assertEqual(self.client.put(f'/api/daily/records/{self.own}',json=self.body).status_code,403)
        self.assertEqual(self.save(visit=self.other).status_code,403)
        self.assertEqual(self.client.get('/api/daily/students/2/history').status_code,403)
        self.assertEqual(self.client.get('/api/daily/analysis').status_code,403)
        self.assertEqual(len(self.client.get('/api/daily').json()['students']),1)
        self.app.dependency_overrides.clear();self.assertEqual(self.client.get('/api/daily').status_code,401)

    def test_record_persists_and_stale_write_cannot_overwrite(self):
        self.assertEqual(self.save().status_code,200)
        self.assertEqual(self.save({**self.body,'note':'stale'}).status_code,409)
        reopened=presence.PresenceStore(self.store.path)
        with patch.object(presence,'_store',return_value=reopened):
            row=self.client.get('/api/daily').json()['students'][0]
            self.assertEqual(row['record'],{k:v for k,v in self.body.items() if k!='version'})
            self.assertEqual(row['version'],1)
        self.assertEqual(self.save({**self.body,'version':1,'note':'Correção'}).status_code,200)
        self.assertEqual(len(self.client.get('/api/daily/students/1/history').json()['records'][0]['edits']),2)

    def test_explicit_assessment_and_conditional_note(self):
        for body in [{'contact':'accompanied','follow_up':False},{**self.body,'pain':'yes'},{**self.body,'outcome':'adapted'},{**self.body,'follow_up':True},{**self.body,'contact':'not_observed'}]:
            self.assertEqual(self.save(body).status_code,422)
        self.assertEqual(self.save({**self.body,'outcome':'unknown','pain':'unknown'}).status_code,200)

    def test_not_observed_is_separate_and_does_not_claim_performance(self):
        self.assertEqual(self.save({**self.body,'contact':'not_observed','note':'Não observei.'}).status_code,200)
        result=self.client.get('/api/daily').json()
        self.assertEqual(result['summary'],{'total':1,'registered':0,'not_observed':1,'pending':0})
        self.assertIsNone(result['students'][0]['record']['pain'])
        self.assertEqual(result['students'][0]['performance'],'Registro diário')

    def test_manager_assignment_teacher_resolution_and_audit(self):
        self.assertEqual(self.adverse().status_code,200);a=self.get_action()
        self.assertEqual(a['status'],'review');self.assertFalse(a['can_edit'])
        self.assertEqual(self.update(a,status='resolved',result='Tentativa').status_code,403)
        self.user=self.admin
        self.assertEqual(self.update(a,status='in_progress',assigned_to=self.teacher['name'],due_date=daily.now().date().isoformat(),instruction='Conversar e registrar retorno.').status_code,200)
        a=self.get_action();self.user=self.teacher
        self.assertEqual(self.update(a,status='resolved',result='').status_code,422)
        self.assertEqual(self.update(a,instruction='Alteração indevida').status_code,403)
        self.assertEqual(self.update(a,status='resolved',result='Retorno realizado.').status_code,200)
        self.user=self.admin;a=self.get_action()
        self.assertEqual(a['result'],'Retorno realizado.');self.assertEqual(len(a['events']),3)
        self.assertEqual(self.update(a,status='in_progress').status_code,200)
        self.assertEqual(self.update(a,result='desatualizado').status_code,409)

    def test_action_dedup_and_reopens_on_new_adverse_report(self):
        self.adverse();self.save({**self.body,'version':1,'pain':'yes','note':'Outro detalhe.'})
        self.assertEqual(len(self.client.get('/api/daily/actions').json()['actions']),1)
        self.user=self.admin;a=self.get_action()
        self.assertEqual(self.update(a,status='resolved',result='Concluído').status_code,200)
        self.user=self.teacher
        self.assertEqual(self.save({**self.body,'version':2,'pain':'yes','note':'Novo relato.'}).status_code,200)
        self.assertEqual(self.get_action()['status'],'review')

    def test_current_assignment_limits_access_but_record_keeps_original_author(self):
        self.save();self.assignments[0]['Professor']=daily.professor_names()[1]
        self.assertEqual(self.client.get('/api/daily').json()['summary']['total'],0)
        self.assertEqual(self.save({**self.body,'version':1}).status_code,403)
        self.user=self.admin;row=self.client.get('/api/daily').json()['students'][0]
        own=next(r for r in self.client.get('/api/daily').json()['students'] if r['client_id']=='1')
        self.assertEqual(own['professor'],self.teacher['name'])

    def test_period_and_pending(self):
        yesterday=daily.now()-timedelta(days=1)
        self.store.ingest([{'CodigoCliente':1,'NomeCliente':'Aluno fictício','Data':yesterday.isoformat(),'DescricaoTipo':'Acesso'}])
        result=self.client.get('/api/daily',params={'start':yesterday.date().isoformat(),'end':daily.now().date().isoformat()}).json()
        self.assertEqual(result['summary']['total'],2)
        self.assertEqual(len(self.client.get('/api/daily?pending=true').json()['students']),1)
        self.assertEqual(self.client.get('/api/daily?start=2026-02-02&end=2026-01-01').status_code,400)

    def test_weekly_writes_retired_and_teacher_cannot_open_week(self):
        self.assertEqual(self.client.get('/api/professor/week').status_code,410)
        self.assertEqual(self.client.post('/api/professor/week/open?start=2026-10-19',headers=self.headers).status_code,410)

    def test_manager_can_create_action_with_no_duplicate(self):
        payload={'visit_id':self.own,'title':'Retorno solicitado pelo gerente'}
        self.assertEqual(self.client.post('/api/daily/actions',json=payload,headers=self.headers).status_code,403)
        self.user=self.admin
        first=self.client.post('/api/daily/actions',json=payload,headers=self.headers).json()
        second=self.client.post('/api/daily/actions',json=payload,headers=self.headers).json()
        self.assertEqual(first,second)

    def test_roster_failure_does_not_fallback_to_stale_permissions(self):
        with patch.object(presence,'_roster_students',side_effect=RuntimeError('offline')):
            self.assertEqual(self.save().status_code,503)
            self.assertEqual(self.client.get('/api/daily').status_code,503)

    def test_assigned_action_is_visible_to_responsible_teacher_outside_portfolio(self):
        self.adverse();self.user=self.admin;a=self.get_action()
        other=daily.professor_names()[1]
        self.assertEqual(self.update(a,status='in_progress',assigned_to=other,due_date=daily.now().date().isoformat(),instruction='Retorno delegado pela gerência.').status_code,200)
        self.user={'role':'professor','name':other,'csrf':'test'}
        assigned=self.get_action();self.assertTrue(assigned['can_edit'])
        self.assertEqual(self.update(assigned,status='resolved',result='Retorno delegado concluído.').status_code,200)
        self.assertEqual(self.client.get('/api/daily/students/1/history').status_code,403)

    def test_first_edit_preserves_original_legacy_record_in_audit(self):
        from backend.app.schemas.presence import DailyAttendanceUpdate
        presence.finalize_attendance(self.own, DailyAttendanceUpdate(desempenho='Regular', observacao='Anotação original'), self.teacher, daily.now())
        self.assertEqual(self.save().status_code,200)
        row=self.client.get('/api/daily/students/1/history').json()['records'][0]
        original=row['edits'][0]['payload']['legacy_before']
        self.assertEqual(original['observation'],'Anotação original')
        self.assertEqual(original['performance'],'Regular')
