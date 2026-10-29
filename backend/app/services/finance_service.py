"""Read-only cash dashboard. Settled movements are the sole actual ledger.

No description-based deduplication, guessing of enrollment IDs, or status-only
recognition of paid expenses. Amounts are integer cents throughout aggregation.
"""
from __future__ import annotations

import calendar
import os
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from nextfit_client import NextFitClient
from .nextfit_session import client as session_client
from .presence_service import _store

TZ = ZoneInfo('America/Sao_Paulo')
_lock = threading.Lock()
_cached = None
_expires = 0
_job_lock = threading.Lock()
_job = None
_job_error = None


def cents(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError('Valor não finito')
        return int((number * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('Valor financeiro inválido na origem') from exc


def day(value):
    if not value or str(value).startswith('0001-'):
        return None
    # NextFit date-only fields use midnight UTC as a civil date, not an instant.
    return date.fromisoformat(str(value)[:10])


def month_shift(value, delta):
    n = value.year * 12 + value.month - 1 + delta
    return date(n // 12, n % 12 + 1, 1)


def unique(rows, field):
    seen = {}
    duplicates = 0
    for row in rows:
        key = row.get(field)
        if key is None:
            raise ValueError('Identificador financeiro ausente')
        if key in seen:
            if seen[key] != row:
                raise ValueError('A origem mudou durante a paginação; atualize a consulta')
            duplicates += 1
        seen[key] = row
    return list(seen.values()), duplicates


def read_v1(path):
    key = os.getenv('NEXTFIT_API_KEY', '').strip()
    base = os.getenv('NEXTFIT_BASE_URL', '').strip()
    if not key or not base:
        raise RuntimeError('Integração financeira NextFit não configurada')
    client = NextFitClient(key, base, os.getenv('NEXTFIT_API_VERSION', '1'))
    rows = []
    for page in range(2000):
        payload = client._get_page(path, {'Skip': page * 30, 'Take': 30})
        batch = payload.get('items')
        if not isinstance(batch, list):
            raise ValueError('Página inválida na API financeira')
        rows.extend(batch)
        if payload.get('temProximaPagina') is False:
            return rows
        if not batch:
            raise ValueError('Paginação incompleta na API financeira')
    raise ValueError('Limite de paginação excedido; totais não publicados')


def read_payables():
    client = session_client(_store())
    rows = []
    total = None
    for page in range(1, 2001):
        payload = client._get('/api/Pagar', {'Page': page, 'Limit': 30})
        batch = payload.get('Content')
        if not isinstance(batch, list) or payload.get('Total') is None:
            raise ValueError('Página de despesas inválida')
        if total is not None and total != payload['Total']:
            raise ValueError('Contas alteradas durante a consulta')
        total = payload['Total']
        rows.extend(batch)
        if payload.get('Last') is True:
            if len(unique(rows, 'Id')[0]) != total:
                raise ValueError('Contas a pagar incompletas')
            return rows
        if not batch:
            raise ValueError('Paginação de despesas incompleta')
    raise ValueError('Limite de despesas excedido')


def source_snapshot():
    global _cached, _expires
    with _lock:
        if _cached is not None and time.monotonic() < _expires:
            return _cached
        with ThreadPoolExecutor(max_workers=3) as pool:
            mov = pool.submit(read_v1, 'MovimentoFinanceiro')
            rec = pool.submit(read_v1, 'ContaReceber')
            pay = pool.submit(read_payables)
            clients = pool.submit(read_v1, 'Pessoa/GetClientes')
            contracts = pool.submit(read_v1, 'ContratoCliente')
            plans = pool.submit(read_v1, 'ContratoBase')
            raw = (mov.result(), rec.result(), pay.result(), clients.result(), contracts.result(), plans.result())
        _cached = normalize(*raw)
        _expires = time.monotonic() + 900
        return _cached


def request_dashboard(selected):
    """Bound HTTP latency while the complete paginated read runs off-request."""
    global _job, _job_error
    with _job_lock:
        if _cached is not None and time.monotonic() < _expires:
            return dashboard(selected, _cached)
        if _job is not None and _job.is_alive():
            return None
        if _job_error:
            _job_error = None
            raise RuntimeError('Consulta financeira anterior falhou; tente novamente')
        def load():
            global _job_error
            try:
                source_snapshot()
            except Exception:
                _job_error = True
        _job = threading.Thread(target=load, name='finance-read', daemon=True)
        _job.start()
        return None


def identifier(value):
    return str(value) if value is not None and value != '' else None


def renewal_candidates(clients, contracts, plans):
    """A dated renewal agenda, never a monetary addition to the forecast."""
    people = {identifier(c['id']): c for c in clients}
    plan_names = {identifier(p['id']): str(p.get('descricao') or '').strip() for p in plans}
    eligible = []
    for contract in contracts:
        cid = identifier(contract.get('codigoCliente'))
        person = people.get(cid, {})
        inactive = person.get('inativo', (person.get('cliente') or {}).get('inativo', False))
        if str(inactive).strip().lower() in ('true', '1', 'sim'):
            continue
        if str(contract.get('status') or '').strip().casefold() != 'ativo' or day(contract.get('dataEncerramento')):
            continue
        due = day(contract.get('dataValidade'))
        if not cid or not due:
            continue
        eligible.append((contract, cid, due))
    result = []
    for contract, cid, due in eligible:
        plan_id = identifier(contract.get('codigoContratoBase'))
        start = day(contract.get('dataInicio'))
        # Keep parallel plans. Suppress only an identifiable contiguous successor
        # for this same plan/client that already extends the coverage.
        successor = any(other['id'] != contract['id'] and other_cid == cid and plan_id is not None
            and identifier(other.get('codigoContratoBase')) == plan_id and other_due > due
            and start is not None and day(other.get('dataInicio')) is not None
            and start < day(other['dataInicio']) <= due + timedelta(days=1)
            for other, other_cid, other_due in eligible)
        if successor:
            continue
        result.append({'id':'contract:'+str(contract['id']), 'client_id':cid,
            'client_name':str(people.get(cid, {}).get('nome') or '').strip() or None,
            'date':due.isoformat(), 'plan':plan_names.get(plan_id) or str(contract.get('descricaoContratoBase') or 'Plano #'+str(plan_id)),
            'basis':'dataValidade', 'source':'ContratoCliente'})
    return sorted(result, key=lambda r:(r['date'], r['client_name'] or '', r['id']))


def normalize(movements, receivables, payables, clients=(), contracts=(), plans=()):
    movements, dm = unique(movements, 'id')
    receivables, dr = unique(receivables, 'id')
    payables, dp = unique(payables, 'Id')
    clients, dc = unique(clients, 'id')
    contracts, dt = unique(contracts, 'id')
    plans, db = unique(plans, 'id')
    names = {identifier(c['id']):str(c.get('nome') or '').strip() for c in clients}
    rows = []
    issues = Counter()
    # Verified NextFit-generated template. Exclude BOTH legs only when each has
    # exactly one opposite counterpart with same amount/timestamp and distinct account.
    # Never infer an internal transfer solely from payment method or fuzzy text.
    transfer_label = 'Transferência de conta Next Fit Pay para conta bancária'
    transfer_groups = {}
    for item in movements:
        if (item.get('descricao') == transfer_label and item.get('status') in ('Efetivado', 'AguardandoEfetivacao')
                and item.get('tipoMetodo') == 'Transferencia'
                and not item.get('codigoCliente') and not item.get('codigoFornecedor')
                and item.get('codigoContaFinanc') is not None):
            key = (item.get('dataEfetivacao'), cents(item['valor']))
            transfer_groups.setdefault(key, []).append(item)
    internal = set()
    pending_internal = set()
    unmatched_internal = set()
    for group in transfer_groups.values():
        if (len(group) == 2 and {r.get('tipo') for r in group} == {'Entrada','Saida'}
                and group[0]['codigoContaFinanc'] != group[1]['codigoContaFinanc']):
            if all(r['status'] == 'Efetivado' for r in group):
                internal.update(r['id'] for r in group)
            else:
                pending_internal.update(r['id'] for r in group)
                issues['pending_internal_transfer'] += 1
        else:
            issues['unmatched_internal_transfer'] += len(group)
            unmatched_internal.update(r['id'] for r in group)

    def add(key, when, amount, direction, state, label, source, client_id=None, review=None):
        if not when:
            issues['missing_date'] += 1
            return
        if amount < 0:
            issues['negative_amount'] += 1
            return
        if amount:
            rows.append(dict(id=key, date=when.isoformat(), amount=amount,
                             direction=direction, state=state, label=label, source=source,
                             client_id=identifier(client_id), client_name=names.get(identifier(client_id)) or None,
                             transfer_review=review))

    for item in movements:
        direction = {'Entrada': 'in', 'Saida': 'out', 'Saída': 'out'}.get(item.get('tipo'))
        status = item.get('status')
        if not direction:
            issues['unknown_movement_type'] += 1
            continue
        if status not in ('Efetivado', 'AguardandoEfetivacao'):
            issues['other_movement_status'] += 1
            continue
        actual = status == 'Efetivado'
        add('mov:'+str(item['id']), day(item.get('dataEfetivacao') if actual else item.get('dataMovimentacao')),
            cents(item['valor']), direction, 'internal' if item['id'] in internal else 'actual' if actual else 'settlement',
            str(item.get('descricao') or 'Movimento financeiro'), 'MovimentoFinanceiro', item.get('codigoCliente'),
            'pending_counterpart' if item['id'] in pending_internal else 'unmatched' if item['id'] in unmatched_internal else None)

    for item in receivables:
        status = item.get('status')
        # Received invoices NEVER enter actual cash a second time.
        if status in ('Recebido', 'Cancelado', 'Renegociado'):
            continue
        if status != 'Aberto':
            issues['unknown_receivable_status'] += 1
            continue
        payment = item.get('receberRecebimento')
        if payment and payment.get('saldo') is None:
            issues['unresolved_receivable_balance'] += 1
            continue
        amount = cents(payment['saldo'] if payment else item['valor'])
        add('rec:'+str(item['id']), day(item.get('dataVencimento')), amount, 'in', 'open',
            str(item.get('descricao') or 'Cobrança '+str(item['id'])), 'ContaReceber', item.get('codigoCliente'))

    for item in payables:
        # Live schema: 1=open; 2 and 3 are not a reliable cash ledger. Settled
        # expenses are already counted from movements. Never add their nominal.
        if item.get('Status') != 1:
            if item.get('Status') not in (0, 2, 3):
                issues['unknown_payable_status'] += 1
            continue
        payment = item.get('PagarPagamento')
        if payment:
            # Do not guess residual balance from nominal or installment status.
            issues['unresolved_payable_balance'] += 1
            continue
        add('pay:'+str(item['Id']), day(item.get('DataVencimento')), cents(item['Valor']),
            'out', 'open', str(item.get('Descricao') or 'Conta '+str(item['Id'])), 'Pagar')

    # A pending settlement and an open invoice may refer to the same cash event.
    # The API has no cross-source key. Keep settlements separately, never add
    # them to projected totals. This sacrifices completeness, not correctness.
    return {'rows': rows, 'renewals':renewal_candidates(clients, contracts, plans), 'read_at': datetime.now(TZ).isoformat(), 'quality': {
        'source_counts': {'movements': len(movements), 'receivables': len(receivables), 'payables': len(payables),
                          'clients':len(clients), 'contracts':len(contracts), 'plans':len(plans)},
        'duplicate_ids_removed': dm + dr + dp + dc + dt + db,
        'internal_transfer_pairs': len(internal)//2,
        'payables_status_counts': dict(Counter(str(x.get('Status')) for x in payables)),
        'issues': dict(issues),
    }}


def dashboard(selected: date, snapshot=None, today=None):
    today = today or datetime.now(TZ).date()
    selected = selected.replace(day=1)
    if selected > month_shift(today, 1) or selected < month_shift(today, -36):
        raise ValueError('Escolha um mês entre os últimos 36 meses e o próximo mês')
    snapshot = snapshot if snapshot is not None else source_snapshot()
    rows = snapshot['rows']
    end = month_shift(selected, 1)
    closed = end <= today.replace(day=1)
    # Future month uses the last complete month, not an incomplete prior month.
    baseline = min(month_shift(selected, -1), month_shift(today, -1))
    baseline_end = month_shift(baseline, 1)
    base_rows = [r for r in rows if r['state'] == 'actual' and r['direction'] == 'in'
                 and baseline.isoformat() <= r['date'] < baseline_end.isoformat()]
    selected_rows = [r for r in rows if selected.isoformat() <= r['date'] < end.isoformat()]
    renewals = [r for r in snapshot.get('renewals', []) if r['date'] >= today.isoformat()]
    weeks = []
    for index, (start_day, end_day) in enumerate(((1,7),(8,15),(16,24),(25,calendar.monthrange(selected.year, selected.month)[1]))):
        start_date, end_date = selected.replace(day=start_day), selected.replace(day=end_day)
        actual_rows = [r for r in selected_rows if r['state'] == 'actual' and start_date.isoformat() <= r['date'] <= end_date.isoformat() and r['date'] <= today.isoformat()]
        pending_rows = [r for r in selected_rows if r['state'] == 'open' and start_date.isoformat() <= r['date'] <= end_date.isoformat() and r['date'] >= today.isoformat()] if not closed else []
        week_rows = actual_rows + pending_rows
        totals = {f'{state}_{direction}': sum(r['amount'] for r in week_rows if r['state'] == state and r['direction'] == direction)
                  for state in ('actual','open') for direction in ('in','out')}
        # Replicate the previous complete month's civil-day cash distribution.
        # Only future dates are projected, avoiding reforecasting elapsed days.
        historical_future = sum(r['amount'] for r in base_rows
            if start_day <= min(int(r['date'][8:10]), end_date.day if index == 3 else 31) <= end_day
            and selected.replace(day=min(int(r['date'][8:10]), calendar.monthrange(selected.year, selected.month)[1])) > today)
        estimate = max(0, historical_future - totals['open_in']) if not closed else 0
        weeks.append({'id': index+1, 'start': start_date.isoformat(), 'end': end_date.isoformat(),
            **totals, 'estimate': estimate, 'historical_future': historical_future,
            'projected_in': totals['actual_in']+totals['open_in']+estimate,
            'projected_out': totals['actual_out']+totals['open_out'],
            'renewals':[r for r in renewals if start_date.isoformat() <= r['date'] <= end_date.isoformat()] if not closed else [],
            'rows': sorted(week_rows, key=lambda r:(r['date'],r['id']))})
    fields = ('actual_in','actual_out','open_in','open_out','estimate','projected_in','projected_out')
    summary = {key: sum(w[key] for w in weeks) for key in fields}
    history = []
    for delta in range(-11,1):
        m = month_shift(today, delta)
        actual = [r for r in rows if r['state']=='actual' and m.isoformat() <= r['date'] < month_shift(m,1).isoformat() and r['date'] <= today.isoformat()]
        history.append({'month':m.strftime('%Y-%m'), 'in':sum(r['amount'] for r in actual if r['direction']=='in'),
                        'out':sum(r['amount'] for r in actual if r['direction']=='out'), 'closed':delta<0})
    return {'month':selected.strftime('%Y-%m'), 'today':today.isoformat(), 'closed':closed,
            'read_at':snapshot['read_at'], 'baseline':{'month':baseline.strftime('%Y-%m'), 'amount':sum(r['amount'] for r in base_rows)},
            'summary':summary, 'weeks':weeks, 'history':history, 'quality':snapshot['quality'],
            'overdue':[r for r in rows if r['state']=='open' and r['date'] < today.isoformat()],
            'settlements':[r for r in selected_rows if r['state']=='settlement'],
            'internal_transfers':[r for r in selected_rows if r['state']=='internal'],
            'transfer_reviews':[r for r in rows if r.get('transfer_review')],
            'transfer_review_effect':sum((r['amount'] if r['direction']=='in' else -r['amount'])
                for r in selected_rows if r.get('transfer_review') and r['state']=='actual' and r['date'] <= today.isoformat()),
            'currency':'BRL', 'unit':'centavos'}
