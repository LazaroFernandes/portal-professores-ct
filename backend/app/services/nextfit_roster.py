"""Current student/teacher relationships from NextFit, never from legacy sheets."""
from __future__ import annotations
import os
import threading
import time
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
from nextfit_client import NextFitClient

# User-confirmed active team, resolved against NextFit users on 2026-10-22.
ACTIVE_PROFESSORS = (
    (28143012, 'Anderson Da Silva Santos'),
    (17884992, 'Katiucy Lauser'),
    (28143132, 'Lucas Eduardo Fiorio'),
    (32248190, 'Lucas Siqueira'),
    (38099218, 'Tais Passos'),
    (38099183, 'Camila Vargas'),
    (38099701, 'Daniel de Oliveira da Rosa'),
)
TTL_SECONDS = 120
_lock = threading.Lock()
_snapshot = None
_expires = 0.0


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '')) if not unicodedata.combining(c)).strip().casefold()


def canonical_professor(name):
    aliases = {normalize(full): full for _, full in ACTIVE_PROFESSORS}
    aliases.update({normalize(short): full for short, (_, full) in zip(
        ('ANDERSON', 'KATIUCY', 'LUCAS FIORIO', 'LUCAS SIQUEIRA', 'TAIS', 'CAMILA', 'DANIEL'), ACTIVE_PROFESSORS)})
    aliases[normalize('Lucas Eduardo Fiore')] = 'Lucas Eduardo Fiorio'
    return aliases.get(normalize(name))


def professor_names():
    return [name for _, name in ACTIVE_PROFESSORS]


def _id(value):
    try: return int(value)
    except (ValueError, TypeError): return None


def build_students(clients, users, contracts):
    user_ids = {_id(u.get('id')) for u in users if not u.get('inativo')}
    expected = dict(ACTIVE_PROFESSORS)
    if not expected.keys() <= user_ids:
        raise RuntimeError('Um professor da equipe ativa não está disponível no NextFit.')
    active_clients = set()
    plans = {}
    modalities = {}
    for contract in contracts:
        if str(contract.get('status') or '').casefold() != 'ativo': continue
        cid = _id(contract.get('codigoCliente'))
        active_clients.add(cid)
        for target, field in ((plans, 'descricaoContratoBase'), (modalities, 'descricaoModalidade')):
            text = str(contract.get(field) or '').strip()
            if text: target.setdefault(cid, set()).add(text)
    result = []
    for client in clients:
        cid = _id(client.get('id'))
        if cid is None: continue
        nested = client.get('cliente') or {}
        pid = _id(nested.get('codigoUsuarioProfessor'))
        result.append({
            'ClienteId': cid, 'Nome': str(client.get('nome') or '').strip(),
            'Professor': expected.get(pid, ''), 'ProfessorId': pid if pid in expected else None,
            'Turno': '', 'Plano': ', '.join(sorted(plans.get(cid, []))),
            'Modalidade': ', '.join(sorted(modalities.get(cid, []))),
            'Status': 'ATIVO' if cid in active_clients and not client.get('inativo', nested.get('inativo', False)) else 'INATIVO',
        })
    return result


def current_roster():
    global _snapshot, _expires
    with _lock:
        if _snapshot is not None and time.monotonic() < _expires:
            return _snapshot
        key = os.environ.get('NEXTFIT_API_KEY', '').strip()
        base = os.environ.get('NEXTFIT_BASE_URL', '').strip()
        if not key or not base:
            raise RuntimeError('API NextFit não configurada para consultar a carteira.')
        client = NextFitClient(key, base, os.environ.get('NEXTFIT_API_VERSION', '1'))
        try:
            users = client.usuarios()
            clients = client.clientes()
            contracts = client.contratos_cliente()
            students = build_students(clients, users, contracts)
        except Exception as exc:
            # No stale teacher assignment fallback: authorization must fail closed.
            raise RuntimeError('Não foi possível atualizar a carteira pela API NextFit.') from exc
        _snapshot = {'students': students, 'source': 'API NextFit',
                     'updated_at': datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()}
        _expires = time.monotonic() + TTL_SECONDS
        return _snapshot
