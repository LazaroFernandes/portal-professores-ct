from __future__ import annotations

import logging
import os
import re
import threading
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from controle_professores.client import load_env, open_nextfit_sync
from nextfit_client import NextFitClient


logger = logging.getLogger("nextfit.frequency")
TIMEZONE = ZoneInfo("America/Sao_Paulo")
CACHE_TAB = "DashboardFrequencia"
WINDOW_DAYS = 3
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


def classify_students(
    clients: list[dict],
    contracts: list[dict],
    plans: list[dict],
    accesses: list[dict],
    now: datetime,
) -> dict:
    if now.tzinfo is None:
        now = now.replace(tzinfo=TIMEZONE)
    else:
        now = now.astimezone(TIMEZONE)
    window_start = now - timedelta(days=WINDOW_DAYS)
    contracts_by_client = _active_contracts(contracts, now)
    plan_names = {
        _to_int(plan.get("id")): str(plan.get("descricao") or "").strip()
        for plan in plans
        if _to_int(plan.get("id")) is not None
    }
    last_access: dict[int, datetime] = {}
    recent: set[int] = set()
    for access in accesses:
        client_id = _to_int(access.get("CodigoCliente"))
        accessed_at = _parse_datetime(access.get("Data"))
        if client_id is None or accessed_at is None or accessed_at > now:
            continue
        if client_id not in last_access or accessed_at > last_access[client_id]:
            last_access[client_id] = accessed_at
        if accessed_at >= window_start:
            recent.add(client_id)

    inactive_students = []
    active_count = 0
    for client in clients:
        client_id = _to_int(client.get("id"))
        if client_id is None or not _is_client_active(client) or client_id not in contracts_by_client:
            continue
        if client_id in recent:
            active_count += 1
            continue
        descriptions = []
        for contract in contracts_by_client[client_id]:
            description = plan_names.get(_to_int(contract.get("codigoContratoBase"))) or str(
                contract.get("descricaoContratoBase") or contract.get("descricaoModalidade") or ""
            ).strip()
            if description and description not in descriptions:
                descriptions.append(description)
        last = last_access.get(client_id)
        inactive_students.append({
            "client_id": client_id,
            "name": str(client.get("nome") or "").strip() or "Não informado",
            "plan": "; ".join(descriptions) or "Não informado",
            "phone": format_phone(client.get("dddFone"), client.get("fone")),
            "last_access": last.isoformat() if last else None,
        })

    inactive_students.sort(key=lambda student: student["name"].casefold())
    return {
        "updated_at": now.isoformat(),
        "window_start": window_start.isoformat(),
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
        "JanelaInicio": snapshot["window_start"],
        "Ativos": snapshot["active_count"],
        "Inativos": snapshot["inactive_count"],
        "ClienteId": "",
        "Nome": "",
        "Plano": "",
        "Telefone": "",
        "UltimoAcesso": "",
    }]
    rows.extend({
        "Tipo": "INATIVO",
        "AtualizadoEm": snapshot["updated_at"],
        "JanelaInicio": snapshot["window_start"],
        "Ativos": snapshot["active_count"],
        "Inativos": snapshot["inactive_count"],
        "ClienteId": student["client_id"],
        "Nome": student["name"],
        "Plano": student["plan"],
        "Telefone": student["phone"],
        "UltimoAcesso": student["last_access"] or "",
    } for student in snapshot["inactive_students"])
    return rows


def read_snapshot() -> dict | None:
    rows = open_nextfit_sync().read_tab_all(CACHE_TAB)
    meta = next((row for row in rows if str(row.get("Tipo") or "") == "META"), None)
    if not meta:
        return None
    students = [{
        "client_id": _to_int(row.get("ClienteId")),
        "name": str(row.get("Nome") or "").strip() or "Não informado",
        "plan": str(row.get("Plano") or "").strip() or "Não informado",
        "phone": str(row.get("Telefone") or "").strip() or "Não informado",
        "last_access": str(row.get("UltimoAcesso") or "").strip() or None,
    } for row in rows if str(row.get("Tipo") or "") == "INATIVO"]
    students.sort(key=lambda student: student["name"].casefold())
    return {
        "updated_at": str(meta.get("AtualizadoEm") or ""),
        "window_start": str(meta.get("JanelaInicio") or ""),
        "active_count": int(meta.get("Ativos") or 0),
        "inactive_count": int(meta.get("Inativos") or 0),
        "inactive_students": students,
    }


def refresh_snapshot(now: datetime | None = None) -> dict:
    if not _refresh_lock.acquire(blocking=False):
        raise RefreshInProgressError("Uma atualização já está em andamento.")
    started = datetime.now(TIMEZONE)
    try:
        logger.info("Iniciando atualização do dashboard de frequência")
        client = _nextfit_client()
        sheet = open_nextfit_sync()
        snapshot = classify_students(
            clients=client.clientes(),
            contracts=client.contratos_cliente(),
            plans=client.contratos_base(),
            accesses=[
                *sheet.read_tab_all("Presencas"),
                *sheet.read_tab_all("PresencasManuais"),
            ],
            now=now or datetime.now(TIMEZONE),
        )
        sheet.write_tab(CACHE_TAB, _cache_rows(snapshot))
        elapsed = (datetime.now(TIMEZONE) - started).total_seconds()
        logger.info(
            "Dashboard de frequência atualizado: ativos=%s inativos=%s duração=%.1fs",
            snapshot["active_count"], snapshot["inactive_count"], elapsed,
        )
        return snapshot
    except Exception:
        logger.exception("Falha ao atualizar o dashboard de frequência")
        raise
    finally:
        _refresh_lock.release()
