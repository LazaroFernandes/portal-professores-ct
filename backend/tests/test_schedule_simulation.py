import json
from datetime import date
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api import schedule
from backend.app.core.security import current_user
from backend.app.services.presence_service import PresenceStore
from backend.app.services import flow_analysis
from backend.app.services.schedule_simulation import KEY, proposed_teachers


def shift(start='05:00', end='06:00', day=0):
    return {'day': day, 'start': start, 'end': end}


def teacher(id='real', source='nextfit', shifts=None):
    return {'id':id,'name':'Test fixture','source':source,'rate':0,'shifts':[shift()] if shifts is None else shifts}


def test_simulation_is_separate_admin_only_and_validated(tmp_path, monkeypatch):
    store=PresenceStore(tmp_path/'simulation.db')
    original=json.dumps({'teachers':[teacher()]})
    store.set_state(schedule.KEY, original)
    monkeypatch.setattr(schedule,'_store',lambda:store)
    c=TestClient(app);url='/api/admin/schedule/simulation'
    assert c.get(url).status_code==401
    app.dependency_overrides[current_user]=lambda:{'role':'admin','csrf':'token'}
    headers={'X-CSRF-Token':'token'}
    body={'overrides':[{'teacher_id':'real','shifts':[shift('08:15','10:45')]}]}
    try:
        assert c.get(url).json()=={'overrides':[],'updated_at':None}
        assert c.put(url,json=body).status_code==403
        assert c.put(url,json=body,headers=headers).status_code==200
        saved=c.get(url).json()
        assert saved['overrides'][0]['shifts'][0]['start']=='08:15:00'
        assert saved['updated_at']
        assert store.state(schedule.KEY)==original
        assert c.put(url,json={'overrides':[{'teacher_id':'unknown','shifts':[]}]},headers=headers).status_code==409
        for invalid in [body['overrides']*2,[{'teacher_id':'real','shifts':[shift(),shift('05:30','07:00')]}],[{'teacher_id':'real','shifts':[shift('08:00','07:00')]}]]:
            assert c.put(url,json={'overrides':invalid},headers=headers).status_code==422
        assert c.put(url,json={'overrides':[{'teacher_id':'real','shifts':[]}]},headers=headers).status_code==200
        assert c.get(url).json()['overrides'][0]['shifts']==[]
        assert c.put(url,json={'overrides':[]},headers=headers).status_code==200
        assert c.get(url).json()['overrides']==[]
        assert store.state(schedule.KEY)==original
        app.dependency_overrides[current_user]=lambda:{'role':'professor','csrf':'token'}
        assert c.get(url).status_code==403
        assert c.put(url,json=body,headers=headers).status_code==403
    finally:
        app.dependency_overrides.clear()


def result(team, overrides):
    rows=[{'CodigoCliente':i,'Data':'2026-10-19T05:00:00-03:00','DescricaoModalidade':'ACESSORIA FIXO','DescricaoTipo':'Acesso'} for i in range(1,9)]
    return flow_analysis.analyze(rows,team,date(2026,10,19),date(2026,10,19),90,overrides)


def test_adjustments_change_only_new_coverage_and_preserve_exact_handover():
    team=[teacher(),teacher('test','test',[shift('05:30','06:00')])]
    base=result(team,[])
    adjusted=result(team,[{'teacher_id':'real','shifts':[shift('05:00','05:30')]}])
    cell=adjusted['rows'][0]['cells'][0]
    assert cell['real_min']==cell['real_max']==1
    assert cell['scheduled']==cell['scheduled_max']==1
    assert cell['test_min']==0 and cell['test']==1
    assert cell['missing4']==1
    for before,after in zip(base['rows'],adjusted['rows']):
        for a,b in zip(before['cells'],after['cells']):
            for key in ('mean','peak','need3','need4','real_min','real_max'):
                assert a[key]==b[key]
    assert team[0]['shifts']==[shift()]


def test_empty_override_is_zero_not_missing_and_restore_inherits():
    team=[teacher()]
    adjusted=result(team,[{'teacher_id':'real','shifts':[]}])
    c=adjusted['rows'][0]['cells'][0]
    assert adjusted['schedule_available'] and c['scheduled']==0 and c['missing4']==2
    assert c['real_min']==1
    assert result(team,[])['rows'][0]['cells'][0]['scheduled']==1
    stale=result(team,[{'teacher_id':'removed','shifts':[shift()]}])
    assert stale['simulation_ignored_teachers']==1 and stale['simulation_adjusted_teachers']==0
    assert stale['rows'][0]['cells'][0]['scheduled']==1
    assert not result([],[])['schedule_available']


def test_overview_reads_latest_simulation_even_with_reused_accesses(tmp_path, monkeypatch):
    store=PresenceStore(tmp_path/'flow.db')
    store.set_state(schedule.KEY,json.dumps({'teachers':[teacher()]}))
    rows=[{'CodigoCliente':1,'Data':'2026-10-19T05:00:00-03:00','DescricaoModalidade':'ACESSORIA FIXO','DescricaoTipo':'Acesso'}]
    monkeypatch.setattr(flow_analysis,'_store',lambda:store)
    monkeypatch.setattr(flow_analysis,'source',lambda *args:(rows,'source-stamp'))
    first=flow_analysis.overview(date(2026,10,19),date(2026,10,19),90)
    store.set_state(KEY,json.dumps({'overrides':[{'teacher_id':'real','shifts':[]}],'updated_at':'saved-stamp'}))
    second=flow_analysis.overview(date(2026,10,19),date(2026,10,19),90)
    assert first['rows'][0]['cells'][0]['scheduled']==1
    assert second['rows'][0]['cells'][0]['scheduled']==0
    assert second['simulation_saved_at']=='saved-stamp' and second['updated_at']=='source-stamp'
