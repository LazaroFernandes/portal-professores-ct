"""Isolated demo: .venv312/bin/python scripts/preview_daily.py (127.0.0.1:8002).

No real credentials, no external integration and no production database.
The SQLite fixture persists between restarts; choose a new --database to reset.
"""
import os
import sys
import json
import argparse
import secrets
from pathlib import Path
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src'), str(ROOT/'backend')]
# Disable dotenv BEFORE importing application modules and replace inherited configuration.
import dotenv
dotenv.load_dotenv = lambda *a, **kw: False
for key in list(os.environ):
    if key.startswith(('NEXTFIT', 'GOOGLE', 'PROFESSOR_', 'APP_PASSWORD', 'DATABASE', 'PG', 'SESSION_', 'COOKIE_', 'SHEETS')):
        os.environ.pop(key)
os.environ.update(APP_ENV='development', COOKIE_SECURE='false', SESSION_SECRET=secrets.token_urlsafe(48),
    APP_PASSWORD='GerenteDemo2026', PROFESSOR_PASSWORDS_JSON=json.dumps({'ANDERSON':'ProfessorDemo2026'}),
    FRONTEND_DIST=str(ROOT/'frontend/dist'))

from backend.app.services import presence_service as presence, daily_workflow as daily
from backend.app.schemas.daily import DailyRecord, ActionUpdate
from backend.app.main import app


def build_demo(path):
    store=presence.PresenceStore(path)
    names=['Ana Exemplo','Bruno Exemplo','Clara Exemplo','Diego Exemplo','Elisa Exemplo','Felipe Exemplo','Gabriela Exemplo','Hugo Exemplo','Iris Exemplo','João Exemplo']
    team=daily.professor_names()
    assignments=[team[0]]*5+[team[1],team[2],team[3],team[4],'']
    roster=[{'ClienteId':str(i+1),'Professor':p} for i,p in enumerate(assignments)]
    presence._store=lambda:store
    presence._roster_students=lambda:roster
    presence.refresh_if_due=lambda *a,**kw:None
    presence.refresh_training_if_due=lambda *a,**kw:None
    def blocked(*a,**kw): raise RuntimeError('Integração externa desativada na prévia local.')
    presence._nextfit_client=blocked
    # Other legacy screens are explicitly unavailable rather than reading real caches.
    from backend.app.services import frequency_service, professor_service
    from backend.app.api import professor_analysis
    frequency_service.read_snapshot=lambda:None
    frequency_service.refresh_snapshot=blocked
    professor_service.week_payload=blocked
    professor_analysis.weekly_analysis=blocked
    # A second guard prevents any accidental outbound HTTP calls in demo mode.
    import requests
    requests.sessions.Session.request=blocked
    import httpx
    httpx.Client.send=blocked
    httpx.AsyncClient.send=blocked
    def training(visit_id,user=None):
        if user and not presence._visit_allowed(visit_id,user): raise PermissionError('Aluno de outra carteira.')
        return {'name':'Ficha demonstrativa','session':1,'total_sessions':3,'weekly_frequency':3,'coach':'Equipe de demonstração','notes':'Conteúdo fictício, apenas para testar a consulta.','exercises':[]}
    presence.training_detail_for_visit=training
    if not store.state('workflow_demo_seeded'):
        moment=daily.now()
        for days in [2,1,0]:
            stamp=(moment-timedelta(days=days)).replace(hour=8,minute=0,second=0,microsecond=0)
            store.ingest([{'CodigoCliente':i+1,'NomeCliente':n,'Data':stamp.isoformat(),'DescricaoTipo':'Acesso'} for i,n in enumerate(names) if days==0 or i<5])
            for row in store.active(stamp,include_finished=True): store.set_student_context(row['id'],assignments[int(row['client_id'])-1],'')
        admin={'role':'admin','name':'Administrador'};teacher={'role':'professor','name':team[0]}
        rows,_=daily.records(admin,moment.date()-timedelta(days=2),moment.date())
        for row in rows:
            cid=int(row['client_id']);day=row['entered_at'][:10]
            if cid==1 and day==moment.date().isoformat(): continue
            if cid==4 or cid>6:continue
            adverse=cid==2
            body={'contact':'not_observed' if cid==3 else 'accompanied','outcome':'adapted' if adverse else 'completed','pain':'yes' if adverse else 'no','note':'Solicitou retorno da equipe após desconforto relatado.' if adverse else 'Não consegui observar o treino neste horário.' if cid==3 else '', 'follow_up':adverse}
            daily.save_record(row['id'],DailyRecord(**body),teacher if cid<=5 else admin)
        for i,action in enumerate(daily.actions(admin)):
            if i==0:continue
            daily.update_action(action['id'],ActionUpdate(version=action['version'],status='in_progress' if i==1 else 'resolved',assigned_to=team[0],due_date=moment.date()-timedelta(days=1),priority='normal',instruction='Conversar com o aluno no próximo atendimento e registrar o retorno.',result='' if i==1 else 'Retorno realizado; acompanhamento concluído no cenário de teste.'),admin)
        store.set_state('workflow_demo_seeded','1')
        store.set_state('last_poll',moment.isoformat())
    app.state.local_demo=True
    return app


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--database',default='/tmp/portal-workflow-demo-20261022.sqlite');parser.add_argument('--port',type=int,default=8002)
    args=parser.parse_args()
    import uvicorn
    uvicorn.run(build_demo(Path(args.database)),host='127.0.0.1',port=args.port,lifespan='off')
