"""One daily record, period analysis and an explicit action lifecycle.

SQLite is for isolated local previews; production shares the existing PostgreSQL
store. Every mutation and audit entry is committed atomically.
"""
import json
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from . import presence_service as presence
from .nextfit_roster import professor_names


class Conflict(ValueError):
    pass


def now():
    return datetime.now(presence.TIMEZONE)


def store():
    s = presence._store()
    sql = (Path(__file__).resolve().parents[2] / 'migrations/002_daily_workflow.sql').read_text()
    with closing(s._connect()) as c:
        with c:
            if s.postgres:
                c.execute(sql)
            else:
                # Execute separately so SQLite does not implicitly commit a transaction.
                for statement in sql.split(';'):
                    if statement.strip(): c.execute(statement)
    return s


def roster():
    return {str(r['ClienteId']): r.get('Professor', '') for r in presence._roster_students()}


def allowed(user, client_id, assignments):
    return user['role'] == 'admin' or assignments.get(str(client_id)) == user['name']


def lock(s, c):
    if s.postgres:
        c.execute('SELECT pg_advisory_xact_lock(72102102)')
    else:
        c.execute('BEGIN IMMEDIATE')


def audit(s, c, entity, entity_id, user, data, stamp):
    s._execute(c, 'INSERT INTO portal_daily_audit VALUES (?, ?, ?, ?, ?, ?, ?)',
               (str(uuid4()), entity, str(entity_id), user['name'], user['role'], json.dumps(data, ensure_ascii=False), stamp))


def _create_action(s, c, visit, user, title, stamp, reopen=False):
    existing = s._execute(c, 'SELECT id, status FROM portal_followup_actions WHERE visit_id = ?', (visit['id'],)).fetchone()
    if existing:
        if reopen and existing['status'] == 'resolved':
            s._execute(c, "UPDATE portal_followup_actions SET status='review', result='', title=?, version=version+1, updated_at=? WHERE id=?", (title[:500], stamp, existing['id']))
            audit(s,c,'action',existing['id'],user,{'event':'reopened','after':{'status':'review','reason':'Novo relato no registro diário'}},stamp)
        return existing['id']
    aid = str(uuid4())
    s._execute(c, '''INSERT INTO portal_followup_actions
        (id, visit_id, client_id, title, assigned_to, status, version, created_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (aid, visit['id'], visit['client_id'], title[:500], 'Gerência', 'review', 1, user['name'], stamp, stamp))
    audit(s, c, 'action', aid, user, {'event': 'created', 'title': title[:500], 'status': 'review'}, stamp)
    return aid


def save_record(visit_id, data, user):
    assignments = roster()
    s = store()
    stamp = now().isoformat()
    with closing(s._connect()) as c:
        with c:
            lock(s, c)
            visit = s._execute(c, 'SELECT * FROM portal_gym_visits WHERE id = ?', (visit_id,)).fetchone()
            if not visit or not allowed(user, visit['client_id'], assignments): raise PermissionError('Atendimento não disponível para seu perfil.')
            old = s._execute(c, 'SELECT * FROM portal_daily_details WHERE visit_id = ?', (visit_id,)).fetchone()
            version = old['version'] if old else 0
            if data.version != version: raise Conflict('O registro foi atualizado por outra pessoa. Reabra antes de editar.')
            legacy_before = None
            if not old:
                legacy_row = s._execute(c, 'SELECT performance, had_pain, pain_description, observation, evolution, finalized_by, finalized_at FROM portal_daily_attendance_records WHERE visit_id=?', (visit_id,)).fetchone()
                legacy_before = dict(legacy_row) if legacy_row else None
            body = data.model_dump(exclude={'version'})
            professor = old['professor_at_record'] if old else assignments.get(visit['client_id'], '')
            s._execute(c, '''INSERT INTO portal_daily_details VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(visit_id) DO UPDATE SET payload=excluded.payload, version=excluded.version,
                actor=excluded.actor, actor_role=excluded.actor_role, updated_at=excluded.updated_at''',
                (visit_id, json.dumps(body, ensure_ascii=False), version+1, user['name'], user['role'], professor, stamp, stamp))
            # Compatibility marker for legacy reads. No fabricated performance rating.
            s._execute(c, '''INSERT INTO portal_daily_attendance_records
                (visit_id,client_id,professor,attendance_date,performance,had_pain,observation,finalized_by,finalized_at,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(visit_id) DO UPDATE SET
                performance=excluded.performance, had_pain=excluded.had_pain, observation=excluded.observation,
                finalized_by=excluded.finalized_by, finalized_at=excluded.finalized_at, updated_at=excluded.updated_at''',
                (visit_id, visit['client_id'], professor, visit['entered_at'][:10], 'Registro diário', int(data.pain == 'yes'),
                 data.note, user['name'], stamp, stamp, stamp))
            s._execute(c, 'UPDATE portal_gym_visits SET finished_at=?, finished_by=? WHERE id=?', (stamp, user['name'], visit_id))
            # Automatic review for reported pain or an interrupted workout, even without an explicit request.
            if data.follow_up or data.pain == 'yes' or data.outcome == 'interrupted':
                _create_action(s, c, visit, user, data.note, stamp, reopen=not old or json.loads(old['payload']) != body)
            audit(s, c, 'record', visit_id, user, {'before': json.loads(old['payload']) if old else None, 'after': body, 'legacy_before': legacy_before, 'version': version+1}, stamp)
    return {'saved': True, 'version': version+1}


def actions(user, assignments=None):
    assignments = roster() if assignments is None else assignments
    s = store()
    with closing(s._connect()) as c:
        rows = s._execute(c, '''SELECT a.*, v.student_name FROM portal_followup_actions a
            JOIN portal_gym_visits v ON v.id=a.visit_id ORDER BY a.created_at DESC''').fetchall()
        result = []
        for raw in rows:
            r = dict(raw)
            if not (allowed(user, r['client_id'], assignments) or r['assigned_to']==user['name']): continue
            r['overdue'] = bool(r['due_date'] and r['due_date'] < now().date().isoformat() and r['status'] != 'resolved')
            r['can_edit'] = user['role']=='admin' or (r['assigned_to']==user['name'] and r['status']=='in_progress')
            r['events'] = [dict(e) for e in s._execute(c, '''SELECT actor, actor_role, payload, created_at
                FROM portal_daily_audit WHERE entity='action' AND entity_id=? ORDER BY created_at''', (r['id'],)).fetchall()]
            for event in r['events']: event['payload'] = json.loads(event['payload'])
            result.append(r)
    return result


def create_action(data, user):
    if user['role'] != 'admin': raise PermissionError('Somente a gerência pode criar uma orientação diretamente.')
    s = store(); stamp=now().isoformat()
    with closing(s._connect()) as c:
        with c:
            lock(s,c)
            visit=s._execute(c,'SELECT * FROM portal_gym_visits WHERE id=?',(data.visit_id,)).fetchone()
            if not visit: raise LookupError('Atendimento não encontrado.')
            aid=_create_action(s,c,visit,user,data.title,stamp)
    return {'id':aid}


def update_action(aid, data, user):
    assignments=roster(); s=store(); stamp=now().isoformat()
    with closing(s._connect()) as c:
        with c:
            lock(s,c)
            raw=s._execute(c,'SELECT * FROM portal_followup_actions WHERE id=?',(aid,)).fetchone()
            if not raw or not (allowed(user, raw['client_id'], assignments) or raw['assigned_to']==user['name']): raise PermissionError('Ação não disponível para seu perfil.')
            old=dict(raw)
            if data.version!=old['version']: raise Conflict('Esta ação mudou. Atualize a lista antes de salvar.')
            due=data.due_date.isoformat() if data.due_date else ''
            if data.assigned_to not in ['Gerência', *professor_names()]: raise ValueError('Responsável não pertence à equipe ativa.')
            if user['role']!='admin':
                if old['assigned_to']!=user['name'] or old['status']!='in_progress': raise PermissionError('Esta ação deve ser atualizada pela gerência ou pelo responsável.')
                if (data.assigned_to!=old['assigned_to'] or due!=old['due_date'] or data.instruction!=old['instruction'] or data.priority!=old['priority'] or data.status=='review'):
                    raise PermissionError('Somente a gerência altera responsável, prazo e orientação.')
            s._execute(c, '''UPDATE portal_followup_actions SET assigned_to=?, due_date=?,status=?, priority=?,
                instruction=?, result=?, version=version+1, updated_at=? WHERE id=?''',
                (data.assigned_to,due,data.status,data.priority,data.instruction,data.result,stamp,aid))
            audit(s,c,'action',aid,user,{'event':'updated','before':{k:old[k] for k in ('status','assigned_to','due_date','instruction','result','priority')},
                'after':data.model_dump(mode='json',exclude={'version'})},stamp)
    return {'saved':True,'version':data.version+1}


def records(user, start, end, pending=False, client_id=None):
    if end<start or (end-start).days>366: raise ValueError('Escolha um período de até 366 dias, com início anterior ao fim.')
    assignments=roster(); s=store()
    with closing(s._connect()) as c:
        sql='''SELECT v.id, v.client_id, v.student_name, v.entered_at, v.professor, v.training_session,
            r.performance, r.observation, r.evolution, r.had_pain, r.pain_description, r.finalized_at, r.finalized_by,
            d.payload, d.version, d.actor, d.actor_role, d.professor_at_record, d.updated_at
            FROM portal_gym_visits v LEFT JOIN portal_daily_attendance_records r ON r.visit_id=v.id
            LEFT JOIN portal_daily_details d ON d.visit_id=v.id WHERE '''
        params=[]
        if pending:
            sql+='v.entered_at < ? AND r.finalized_at IS NULL';params=[now().date().isoformat()]
        elif client_id is not None:
            if not allowed(user,client_id,assignments): raise PermissionError('Histórico não disponível para seu perfil.')
            sql+='v.client_id=?';params=[str(client_id)]
        else:
            sql+='v.entered_at >= ? AND v.entered_at < ?';params=[start.isoformat(),(end+timedelta(days=1)).isoformat()]
        sql+=' ORDER BY v.entered_at DESC'
        rows=s._execute(c,sql,params).fetchall()
        result=[]
        for raw in rows:
            r=dict(raw)
            if not allowed(user,r['client_id'],assignments): continue
            r['current_professor']=assignments.get(r['client_id'],'')
            r['professor']=r['professor_at_record'] if r['payload'] else (r['professor'] or '')
            if r['entered_at'][:10]==now().date().isoformat() and not r['finalized_at']: r['professor']=r['current_professor']
            payload = r.pop('payload')
            r['record']=json.loads(payload) if payload else None
            r['version']=r['version'] or 0
            r['legacy']=bool(r['finalized_at'] and not r['record'])
            r['status']='pending' if not r['finalized_at'] else ('not_observed' if r['record'] and r['record']['contact']=='not_observed' else 'registered')
            r['edits'] = [dict(e) for e in s._execute(c, "SELECT actor,created_at,payload FROM portal_daily_audit WHERE entity='record' AND entity_id=? ORDER BY created_at",(str(r['id']),)).fetchall()] if client_id is not None else []
            for edit in r['edits']: edit['payload']=json.loads(edit['payload'])
            result.append(r)
    return result, actions(user,assignments)


def overview(user,start,end,pending=False):
    rows,all_actions=records(user,start,end,pending)
    open_actions=[a for a in all_actions if a['status']!='resolved']
    for r in rows: r['open_actions']=[a for a in open_actions if a['client_id']==r['client_id']]
    def counts(items):
        return {'total':len(items),'registered':sum(r['status']=='registered' for r in items),
                'not_observed':sum(r['status']=='not_observed' for r in items),'pending':sum(r['status']=='pending' for r in items)}
    groups=defaultdict(list)
    for r in rows: groups[r['professor'] or 'Sem responsável'].append(r)
    return {'start':start.isoformat(),'end':end.isoformat(),'students':rows,'summary':counts(rows),
        'professors':professor_names(),'by_professor':[{'name':name,**counts(items)} for name,items in sorted(groups.items())],
        'actions':open_actions,'last_access_sync':presence._store().state('last_poll'),
        'sync_error':presence._last_sync_error,'preview':False}
