from datetime import date
from backend.app.services.flow_analysis import analyze

def row(cid,stamp,mode='ACESSORIA FIXO'):
 return {'CodigoCliente':cid,'Data':stamp,'DescricaoModalidade':mode,'DescricaoTipo':'Acesso'}

def cell(result,time,day=0): return next(r for r in result['rows'] if r['time']==time)['cells'][day]

def test_dedupe_denominator_minutes_and_test_separation():
 teachers=[{'source':'nextfit','shifts':[{'day':0,'start':'08:30','end':'09:00'}]},{'source':'test','shifts':[{'day':0,'start':'08:00','end':'10:00'}]}]
 rows=[row(1,'2026-10-19T08:00:00-03:00'),row(1,'2026-10-19T08:05:00-03:00'),row(2,'2026-10-19T08:00:00-03:00'),row(3,'2026-10-19T08:00:00-03:00','HYROX')]
 r=analyze(rows,teachers,date(2026,10,19),date(2026,10,26),90)
 c=cell(r,'08:00');assert c['mean']==1 and c['days']==2 and c['peak']==2
 assert c['scheduled']==1 and c['scheduled_max']==2 and c['test']==1 and c['missing3']==0 and c['missing3_min']==0
 assert c['real_min']==0 and c['real_max']==1 and r['coverage_includes_test'] is True
 c=cell(r,'09:00');assert c['scheduled']==1 and c['missing4']==0

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
 assert cell(r,'09:00')['mean']==0.25
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

def test_full_hour_late_entries_dedup_and_peak_between_boundaries():
 rows=[row(1,'2026-10-19T05:30:00-03:00'),row(1,'2026-10-19T05:30:00-03:00'),row(2,'2026-10-19T05:45:00-03:00')]
 r=analyze(rows,[],date(2026,10,19),date(2026,10,19),60)
 c=cell(r,'05:00');assert c['mean']==0.75 and c['peak']==2
 assert r['rows'][0]['label']=='05:00–06:00' and len(r['rows'])==17
 assert cell(r,'06:00')['mean']==1.25

def test_teacher_handover_does_not_sum_non_simultaneous_people():
 teachers=[{'source':'nextfit','shifts':[{'day':0,'start':'05:00','end':'05:30'}]}, {'source':'nextfit','shifts':[{'day':0,'start':'05:30','end':'06:00'}]}]
 c=cell(analyze([row(1,'2026-10-19T05:15:00-03:00')],teachers,date(2026,10,19),date(2026,10,19),90),'05:00')
 assert c['scheduled']==1 and c['scheduled_max']==1 and c['missing4']==0

def test_seconds_and_exact_hour_boundary_exclusion():
 rows=[row(1,'2026-10-19T05:59:30-03:00'),row(2,'2026-10-19T06:00:00-03:00')]
 c=cell(analyze(rows,[],date(2026,10,19),date(2026,10,19),60),'05:00')
 assert abs(c['mean']-1/120)<1e-10 and c['peak']==1

def test_upstream_records_outside_selected_period_do_not_confirm_zero():
 r=analyze([row(1,'2026-10-20T05:30:00-03:00')],[],date(2026,10,19),date(2026,10,19),90)
 assert not r['data_available'] and r['eligible_records']==0
 assert cell(r,'05:00')['mean'] is None

def test_only_test_teachers_make_coverage_available_with_partial_hour_deficits():
 teachers=[{'source':'test','shifts':[{'day':0,'start':'05:30','end':'06:00'}]} for _ in range(2)]
 rows=[row(i,'2026-10-19T05:00:00-03:00') for i in range(1,10)]
 r=analyze(rows,teachers,date(2026,10,19),date(2026,10,19),90)
 c=cell(r,'05:00')
 assert r['schedule_available'] and c['scheduled']==0 and c['scheduled_max']==2
 assert c['test_min']==0 and c['test']==2 and c['real_max']==0
 assert c['need4']==3 and c['missing4']==3 and c['missing4_min']==1
 assert c['missing3']==3 and c['missing3_min']==1

def test_real_to_test_handover_keeps_total_coverage_continuous():
 teachers=[{'source':'nextfit','shifts':[{'day':0,'start':'05:00','end':'05:30'}]},{'source':'test','shifts':[{'day':0,'start':'05:30','end':'06:00'}]}]
 c=cell(analyze([row(1,'2026-10-19T05:00:00-03:00')],teachers,date(2026,10,19),date(2026,10,19),90),'05:00')
 assert c['scheduled']==1 and c['scheduled_max']==1 and c['missing4']==0
 assert c['real_min']==0 and c['test_min']==0
