"""Time-weighted occupancy over complete hourly intervals; no personal data in results."""
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
    period_start=datetime.combine(start,datetime.min.time(),TIMEZONE)
    period_end=datetime.combine(end+timedelta(days=1),datetime.min.time(),TIMEZONE)
    intervals = defaultdict(list)
    invalid = 0
    missing_mode = 0
    eligible = 0
    for r in rows:
        if _normalized(r.get('DescricaoTipo')) != 'acesso' or str(r.get('Inativo',False)).lower() in ('true','1'): continue
        if not r.get('DescricaoModalidade') or r.get('DescricaoModalidade') == 'null': missing_mode += 1
        if _normalized(r.get('DescricaoModalidade')) not in MODES: continue
        stamp = _parse_datetime(r.get('Data'))
        if stamp and (stamp>=period_end or stamp+timedelta(minutes=stay)<=period_start): continue
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
    def count(team,day,minute):
        return sum(any(s['day']==day and clock(s['start'])<=minute<clock(s['end']) for s in t['shifts']) for t in team)
    def coverage(team,day,begin,finish):
        boundaries={begin,finish}
        for t in team:
            for s in t['shifts']:
                if s['day']==day:
                    boundaries.update(v for v in (clock(s['start']),clock(s['end'])) if begin<v<finish)
        points=sorted(boundaries)
        counts=[count(team,day,p) for p in points[:-1]]
        return min(counts),max(counts)
    def occupancy(begin,finish):
        # Unioned person intervals prevent duplicate turnstile passages from
        # counting the same person twice. Integrate seconds, not hourly samples.
        seconds=0.0
        events=defaultdict(int)
        for a,b in merged:
            left,right=max(a,begin),min(b,finish)
            if left<right:
                seconds+=(right-left).total_seconds()
                events[left]+=1
                events[right]-=1
        current=peak=0
        for stamp in sorted(events):
            current+=events[stamp]
            peak=max(peak,current)
        return seconds,peak
    result=[]
    for minute in range(300,1320,60):
        cells=[]
        for day, ds in enumerate(groups):
            values=[]
            peaks=[]
            for d in ds:
                begin=datetime.combine(d,datetime.min.time(),TIMEZONE)+timedelta(minutes=minute)
                mean_day,peak_day=occupancy(begin,begin+timedelta(hours=1))
                values.append(mean_day)
                peaks.append(peak_day)
            valid=bool(values) and bool(eligible) and not invalid
            mean=sum(values)/(3600*len(values)) if valid else None
            low,high=coverage(real,day,minute,minute+60) if scheduled else (None,None)
            test_low,test_high=coverage(test,day,minute,minute+60)
            n4=math.ceil(mean/4) if mean is not None else None
            n3=math.ceil(mean/3) if mean is not None else None
            cells.append({'mean':mean,'peak':max(peaks) if valid else None,'days':len(ds),
                'need4':n4,'need3':n3,'scheduled':low,'scheduled_max':high,
                'test':test_high,'test_min':test_low,
                'missing4':max(0,n4-low) if n4 is not None and low is not None else None,
                'missing4_min':max(0,n4-high) if n4 is not None and high is not None else None,
                'missing3':max(0,n3-low) if n3 is not None and low is not None else None,
                'missing3_min':max(0,n3-high) if n3 is not None and high is not None else None})
        label=f'{minute//60:02}:00–{minute//60+1:02}:00'
        result.append({'time':f'{minute//60:02}:00','label':label,'cells':cells})
    return {'method':'hourly_time_weighted_v2','rows':result,'dates':[[d.isoformat() for d in ds] for ds in groups],'start':start.isoformat(),'end':end.isoformat(),'stay':stay,'eligible_records':eligible,'invalid_records':invalid,'unclassified_records':missing_mode,'schedule_available':scheduled,'data_available':bool(eligible) and not invalid}

def overview(start,end,stay):
    rows,stamp=source(start,end)
    raw=_store().state('teacher_schedule_v1')
    teachers=json.loads(raw).get('teachers',[]) if raw else []
    result=analyze(rows,teachers,start,end,stay)
    result['updated_at']=stamp
    result['schedule_read_at']=datetime.now(TIMEZONE).isoformat()
    return result
