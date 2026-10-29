from datetime import date
from backend.app.services.flow_analysis import analyze

def row(cid,stamp,mode='ACESSORIA FIXO'):
 return {'CodigoCliente':cid,'Data':stamp,'DescricaoModalidade':mode,'DescricaoTipo':'Acesso'}

def cell(result,time,day=0): return next(r for r in result['rows'] if r['time']==time)['cells'][day]

def test_dedupe_denominator_minutes_and_test_separation():
 teachers=[{'source':'nextfit','shifts':[{'day':0,'start':'08:30','end':'09:00'}]},{'source':'test','shifts':[{'day':0,'start':'08:00','end':'10:00'}]}]
 rows=[row(1,'2026-10-19T08:00:00-03:00'),row(1,'2026-10-19T08:05:00-03:00'),row(2,'2026-10-19T08:00:00-03:00'),row(3,'2026-10-19T08:00:00-03:00','HYROX')]
 r=analyze(rows,teachers,date(2026,10,19),date(2026,10,26),90)
 c=cell(r,'08:30');assert c['mean']==1 and c['days']==2 and c['peak']==2
 assert c['scheduled']==1 and c['test']==1 and c['missing3']==0
 c=cell(r,'09:00');assert c['scheduled']==0 and c['missing4']==1

def test_round_up_and_unavailable():
 rows=[row(i,'2026-10-19T08:00:00-03:00') for i in range(1,10)]
 r=analyze(rows,[],date(2026,10,19),date(2026,10,19),60)
 c=cell(r,'08:00');assert c['need4']==3 and c['need3']==3 and c['scheduled'] is None and c['missing4'] is None
 assert cell(r,'09:00')['mean']==0
 assert cell(analyze([],[],date(2026,10,19),date(2026,10,19),90),'08:00')['mean'] is None
 assert cell(analyze([row(None,'bad')],[],date(2026,10,19),date(2026,10,19),90),'08:00')['mean'] is None

def test_previous_day_and_stay():
 rows=[row(1,'2026-10-18T23:30:00-03:00'),row(2,'2026-10-19T07:45:00-03:00')]
 r=analyze(rows,[],date(2026,10,19),date(2026,10,19),90)
 assert cell(r,'09:00')['mean']==1
 assert cell(analyze(rows,[],date(2026,10,19),date(2026,10,19),60),'09:00')['mean']==0

def test_access_validation_and_source_failure(monkeypatch):
 from fastapi.testclient import TestClient
 from backend.app.main import app
 from backend.app.core.security import current_user
 from backend.app.api import flow
 c=TestClient(app);url='/api/admin/flow?start=2026-10-19&end=2026-10-20'
 assert c.get(url).status_code==401
 app.dependency_overrides[current_user]=lambda:{'role':'professor'}
 try:
  assert c.get(url).status_code==403
  app.dependency_overrides[current_user]=lambda:{'role':'admin'}
  assert c.get(url+'&stay=45').status_code==422
  assert c.get('/api/admin/flow?start=2026-10-20&end=2026-10-19').status_code==422
  def fail(*args): raise RuntimeError('private upstream exception')
  monkeypatch.setattr(flow,'overview',fail)
  r=c.get(url);assert r.status_code==503 and 'private' not in r.text
 finally: app.dependency_overrides.clear()
