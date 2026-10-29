"""Estimated occupancy at explicit time instants; no personal data in results."""
import json
import math
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from .presence_service import TIMEZONE, _nextfit_client, _store
from .frequency_service import _normalized, _parse_datetime

MODES = {'acessoria fixo', 'consultoria livre'}
_lock = threading.Lock()
_cache = {}

def source(start, end):
    key = (start.isoformat(), end.isoformat())
    with _lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < 300:
            return cached[1], cached[2]
        rows = _nextfit_client().presencas(datetime.combine(start, datetime.min.time(), TIMEZONE) - timedelta(minutes=90), datetime.combine(end + timedelta(days=1), datetime.min.time(), TIMEZONE), strict=True)
        stamp = datetime.now(TIMEZONE).isoformat()
        _cache.clear()
        _cache[key] = (time.monotonic(), rows, stamp)
        return rows, stamp

def analyze(rows, teachers, start, end, stay):
    dates = [start + timedelta(days=i) for i in range((end-start).days+1)]
    groups = [[d for d in dates if d.weekday()==day] for day in range(7)]
    intervals = defaultdict(list)
    invalid = 0
    missing_mode = 0
    eligible = 0
    for r in rows:
        if _normalized(r.get('DescricaoTipo')) != 'acesso' or str(r.get('Inativo',False)).lower() in ('true','1'): continue
        if not r.get('DescricaoModalidade') or r.get('DescricaoModalidade') == 'null': missing_mode += 1
        if _normalized(r.get('DescricaoModalidade')) not in MODES: continue
        stamp = _parse_datetime(r.get('Data'))
        cid = r.get('CodigoCliente')
        if stamp is None or not cid: invalid += 1; continue
        intervals[str(cid)].append((stamp,stamp+timedelta(minutes=stay)))
        eligible += 1
    merged=[]
    for spans in intervals.values():
        union=[]
        for a,b in sorted(spans):
            if union and a <= union[-1][1]: union[-1]=(union[-1][0], max(b,union[-1][1]))
            else: union.append((a,b))
        merged.extend(union)
    def clock(raw):
        parts=raw.split(':'); return int(parts[0])*60+int(parts[1])
    real=[t for t in teachers if t.get('source')=='nextfit']
    test=[t for t in teachers if t.get('source')=='test']
    scheduled=any(t.get('shifts') for t in real)
    samples=set(range(300,1321,60))
    for t in teachers:
        for s in t.get('shifts',[]):
            samples.update(v for v in (clock(s['start']),clock(s['end'])) if 300<=v<=1320)
    def count(team,day,minute):
        return sum(any(s['day']==day and clock(s['start'])<=minute<clock(s['end']) for s in t['shifts']) for t in team)
    result=[]
    for minute in sorted(samples):
        cells=[]
        for day, ds in enumerate(groups):
            values=[]
            for d in ds:
                instant=datetime.combine(d,datetime.min.time(),TIMEZONE)+timedelta(minutes=minute)
                values.append(sum(a<=instant<b for a,b in merged))
            valid=bool(values) and bool(eligible) and not invalid
            mean=sum(values)/len(values) if valid else None
            coverage=count(real,day,minute) if scheduled else None
            n4=math.ceil(mean/4) if mean is not None else None
            n3=math.ceil(mean/3) if mean is not None else None
            cells.append({'mean':mean,'peak':max(values) if valid else None,'days':len(ds),'need4':n4,'need3':n3,'scheduled':coverage,'test':count(test,day,minute),'missing4':max(0,n4-coverage) if n4 is not None and coverage is not None else None,'missing3':max(0,n3-coverage) if n3 is not None and coverage is not None else None})
        result.append({'time':f'{minute//60:02}:{minute%60:02}','cells':cells})
    return {'rows':result,'dates':[[d.isoformat() for d in ds] for ds in groups],'start':start.isoformat(),'end':end.isoformat(),'stay':stay,'eligible_records':eligible,'invalid_records':invalid,'unclassified_records':missing_mode,'schedule_available':scheduled,'data_available':bool(eligible) and not invalid}

def overview(start,end,stay):
    rows,stamp=source(start,end)
    raw=_store().state('teacher_schedule_v1')
    teachers=json.loads(raw).get('teachers',[]) if raw else []
    result=analyze(rows,teachers,start,end,stay)
    result['updated_at']=stamp
    result['schedule_read_at']=datetime.now(TIMEZONE).isoformat()
    return result
