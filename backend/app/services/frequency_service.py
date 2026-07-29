from __future__ import annotations

import logging
import os
import re
import threading
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from controle_professores import postgres_data
from controle_professores.client import load_env, open_nextfit_sync
from nextfit_client import NextFitClient


logger = logging.getLogger("nextfit.frequency")
TIMEZONE = ZoneInfo("America/Sao_Paulo")
CACHE_TAB = "DashboardVencimentos"
GRACE_DAYS = 3
_refresh_lock = threading.Lock()


class RefreshInProgressError(RuntimeError):
    pass


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_true(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "verdadeiro", "sim"}


def _is_client_active(client: dict) -> bool:
    nested = client.get("cliente") or {}
    return not _is_true(client.get("inativo", nested.get("inativo")))


def _normalized(value) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    return "".join(char for char in text if unicodedata.category(char) != "Mn").strip().casefold()


def _parse_datetime(value, timezone: ZoneInfo = TIMEZONE) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def _active_contracts(contracts: list[dict], now: datetime) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = {}
    for contract in contracts:
        client_id = _to_int(contract.get("codigoCliente"))
        if client_id is None or _normalized(contract.get("status")) != "ativo":
            continue
        ended_at = _parse_datetime(contract.get("dataEncerramento"))
        if ended_at and ended_at <= now:
            continue
        result.setdefault(client_id, []).append(contract)
    return result


def _contracts_by_client(contracts: list[dict]) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = {}
    for contract in contracts:
        client_id = _to_int(contract.get("codigoCliente"))
        if client_id is not None:
            result.setdefault(client_id, []).append(contract)
    return result


def _contract_sort_key(contract: dict) -> tuple[float, int]:
    started_at = (
        _parse_datetime(contract.get("dataInicio"))
        or _parse_datetime(contract.get("dataCriacao"))
    )
    return (
        started_at.timestamp() if started_at else float("-inf"),
        _to_int(contract.get("id")) or -1,
    )


def classify_students(
    clients: list[dict],
    contracts: list[dict],
    plans: list[dict],
    receivables: list[dict],
    now: datetime,
) -> dict:
    if now.tzinfo is None:
        now = now.replace(tzinfo=TIMEZONE)
    else:
        now = now.astimezone(TIMEZONE)
    active_contracts_by_client = _active_contracts(contracts, now)
    all_contracts_by_client = _contracts_by_client(contracts)
    plan_names = {
        _to_int(plan.get("id")): str(plan.get("descricao") or "").strip()
        for plan in plans
        if _to_int(plan.get("id")) is not None
    }
    overdue_limit = (now - timedelta(days=GRACE_DAYS)).date()
    overdue_by_client: dict[int, datetime] = {}
    for receivable in receivables:
        if _normalized(receivable.get("status")) != "aberto":
            continue
        client_id = _to_int(receivable.get("codigoCliente"))
        due_at = _parse_datetime(receivable.get("dataVencimento"))
        if client_id is None or due_at is None or due_at.date() > overdue_limit:
            continue
        if client_id not in overdue_by_client or due_at < overdue_by_client[client_id]:
            overdue_by_client[client_id] = due_at

    for client_id, client_contracts in all_contracts_by_client.items():
        latest_contract = max(client_contracts, key=_contract_sort_key)
        if _normalized(latest_contract.get("status")) != "bloqueado":
            continue
        expires_at = _parse_datetime(latest_contract.get("dataValidade"))
        if expires_at is None or expires_at.date() > overdue_limit:
            continue
        if client_id not in overdue_by_client or expires_at < overdue_by_client[client_id]:
            overdue_by_client[client_id] = expires_at

    clients_by_id = {
        client_id: client
        for client in clients
        if (client_id := _to_int(client.get("id"))) is not None
    }
    inactive_students = []
    active_count = 0
    for client_id, client in clients_by_id.items():
        if not _is_client_active(client) or client_id not in active_contracts_by_client:
            continue
        if client_id not in overdue_by_client:
            active_count += 1

    for client_id, due_at in overdue_by_client.items():
        client = clients_by_id.get(client_id)
        if client is None:
            continue
        descriptions = []
        for contract in all_contracts_by_client.get(client_id, []):
            description = plan_names.get(_to_int(contract.get("codigoContratoBase"))) or str(
                contract.get("descricaoContratoBase") or contract.get("descricaoModalidade") or ""
            ).strip()
            if description and description not in descriptions:
                descriptions.append(description)
        inactive_students.append({
            "client_id": client_id,
            "name": str(client.get("nome") or "").strip() or "Não informado",
            "plan": "; ".join(descriptions) or "Não informado",
            "phone": format_phone(client.get("dddFone"), client.get("fone")),
            "due_date": due_at.date().isoformat(),
        })

    inactive_students.sort(key=lambda student: student["name"].casefold())
    return {
        "updated_at": now.isoformat(),
        "grace_days": GRACE_DAYS,
        "active_count": active_count,
        "inactive_count": len(inactive_students),
        "inactive_students": inactive_students,
    }


def format_phone(area_code, number) -> str:
    digits = re.sub(r"\D", "", f"{area_code or ''}{number or ''}")
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return "Não informado"


def _nextfit_client() -> NextFitClient:
    load_env()
    api_key = os.environ.get("NEXTFIT_API_KEY", "").strip()
    base_url = os.environ.get("NEXTFIT_BASE_URL", "").strip()
    if not api_key or not base_url:
        raise RuntimeError("Integração Nextfit não configurada no servidor.")
    return NextFitClient(
        api_key=api_key,
        base_url=base_url,
        version=os.environ.get("NEXTFIT_API_VERSION", "1"),
    )


def _cache_rows(snapshot: dict) -> list[dict]:
    rows = [{
        "Tipo": "META",
        "AtualizadoEm": snapshot["updated_at"],
        "DiasTolerancia": snapshot["grace_days"],
        "Ativos": snapshot["active_count"],
        "Inativos": snapshot["inactive_count"],
        "ClienteId": "",
        "Nome": "",
        "Plano": "",
        "Telefone": "",
        "Vencimento": "",
    }]
    rows.extend({
        "Tipo": "INATIVO",
        "AtualizadoEm": snapshot["updated_at"],
        "DiasTolerancia": snapshot["grace_days"],
        "Ativos": snapshot["active_count"],
        "Inativos": snapshot["inactive_count"],
        "ClienteId": student["client_id"],
        "Nome": student["name"],
        "Plano": student["plan"],
        "Telefone": student["phone"],
        "Vencimento": student["due_date"],
    } for student in snapshot["inactive_students"])
    return rows


def read_snapshot() -> dict | None:
    if postgres_data.enabled():
        return _snapshot_from_postgres()
    rows = open_nextfit_sync().read_tab_all(CACHE_TAB)
    meta = next((row for row in rows if str(row.get("Tipo") or "") == "META"), None)
    if not meta:
        return None
    students = [{
        "client_id": _to_int(row.get("ClienteId")),
        "name": str(row.get("Nome") or "").strip() or "Não informado",
        "plan": str(row.get("Plano") or "").strip() or "Não informado",
        "phone": str(row.get("Telefone") or "").strip() or "Não informado",
        "due_date": str(row.get("Vencimento") or "").strip() or None,
    } for row in rows if str(row.get("Tipo") or "") == "INATIVO"]
    students.sort(key=lambda student: student["name"].casefold())
    return {
        "updated_at": str(meta.get("AtualizadoEm") or ""),
        "grace_days": int(meta.get("DiasTolerancia") or GRACE_DAYS),
        "active_count": int(meta.get("Ativos") or 0),
        "inactive_count": int(meta.get("Inativos") or 0),
        "inactive_students": students,
    }


def refresh_snapshot(now: datetime | None = None) -> dict:
    if not _refresh_lock.acquire(blocking=False):
        raise RefreshInProgressError("Uma atualização já está em andamento.")
    started = datetime.now(TIMEZONE)
    try:
        logger.info("Iniciando atualização do dashboard de vencimentos")
        if postgres_data.enabled():
            snapshot = _snapshot_from_postgres(now=now)
            if snapshot is None:
                raise RuntimeError("Dados do NextFit ainda nao encontrados no PostgreSQL.")
            elapsed = (datetime.now(TIMEZONE) - started).total_seconds()
            logger.info(
                "Dashboard de vencimentos lido do PostgreSQL: ativos=%s inativos=%s duracao=%.1fs",
                snapshot["active_count"], snapshot["inactive_count"], elapsed,
            )
            return snapshot
        client = _nextfit_client()
        sheet = open_nextfit_sync()
        snapshot = classify_students(
            clients=client.clientes(),
            contracts=client.contratos_cliente(),
            plans=client.contratos_base(),
            receivables=client.contas_receber(),
            now=now or datetime.now(TIMEZONE),
        )
        sheet.write_tab(CACHE_TAB, _cache_rows(snapshot))
        elapsed = (datetime.now(TIMEZONE) - started).total_seconds()
        logger.info(
            "Dashboard de vencimentos atualizado: ativos=%s inativos=%s duração=%.1fs",
            snapshot["active_count"], snapshot["inactive_count"], elapsed,
        )
        return snapshot
    except Exception:
        logger.exception("Falha ao atualizar o dashboard de vencimentos")
        raise
    finally:
        _refresh_lock.release()


def _snapshot_from_postgres(now: datetime | None = None) -> dict | None:
    clients = postgres_data.read_raw_table("nf_clientes")
    contracts = postgres_data.read_raw_table("nf_contratos_cliente")
    plans = postgres_data.read_raw_table("nf_contratos_base")
    receivables = postgres_data.read_raw_table("nf_contas_receber")
    if not clients or not contracts:
        return None
    return classify_students(
        clients=clients,
        contracts=contracts,
        plans=plans,
        receivables=receivables,
        now=now or datetime.now(TIMEZONE),
    )
