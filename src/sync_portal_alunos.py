from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from controle_professores import postgres_data
from controle_professores.sync_alunos import _inferir_turno, _join_unicos, _modalidade_de_plano, _norm


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_true(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "verdadeiro", "sim"}


def _is_active_client(client: dict[str, Any], active_contract_clients: set[int]) -> bool:
    nested = client.get("cliente") or {}
    if _is_true(client.get("inativo", nested.get("inativo"))):
        return False
    client_id = _to_int(client.get("id"))
    return client_id is not None and client_id in active_contract_clients


def _existing_by_client(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        client_id = _to_int(row.get("ClienteId"))
        if client_id is not None:
            result[client_id] = row
    return result


def build_portal_rows(
    *,
    clients: list[dict[str, Any]],
    users: list[dict[str, Any]],
    contracts: list[dict[str, Any]],
    contract_bases: list[dict[str, Any]],
    existing_rows: list[dict[str, Any]],
    now_iso: str,
) -> list[dict[str, Any]]:
    existing = _existing_by_client(existing_rows)
    user_names = {
        _to_int(user.get("id")): str(user.get("nome") or "").strip()
        for user in users
        if _to_int(user.get("id")) is not None
    }
    plan_names = {
        _to_int(base.get("id")): str(base.get("descricao") or "").strip()
        for base in contract_bases
        if _to_int(base.get("id")) is not None
    }

    active_contract_clients: set[int] = set()
    plans_by_client: dict[int, list[str]] = {}
    modalities_by_client: dict[int, list[str]] = {}
    for contract in contracts:
        if str(contract.get("status") or "").strip() != "Ativo":
            continue
        client_id = _to_int(contract.get("codigoCliente"))
        if client_id is None:
            continue
        active_contract_clients.add(client_id)
        base_id = _to_int(contract.get("codigoContratoBase"))
        plan = (
            plan_names.get(base_id)
            or str(contract.get("descricaoContratoBase") or "").strip()
            or str(contract.get("descricaoModalidade") or "").strip()
        )
        if not plan:
            continue
        plans_by_client.setdefault(client_id, []).append(plan)
        modality = _modalidade_de_plano(plan)
        if modality:
            modalities_by_client.setdefault(client_id, []).append(modality)

    rows: list[dict[str, Any]] = []
    for client in clients:
        client_id = _to_int(client.get("id"))
        name = str(client.get("nome") or "").strip()
        if client_id is None or not name:
            continue

        nested = client.get("cliente") or {}
        nextfit_professor = user_names.get(_to_int(nested.get("codigoUsuarioProfessor")), "")
        current = existing.get(client_id, {})
        current_turn = str(current.get("Turno") or "").strip()
        current_professor = str(current.get("Professor") or "").strip()
        plans = plans_by_client.get(client_id, [])

        rows.append({
            "ClienteId": client_id,
            "Nome": name,
            "Turno": current_turn or _inferir_turno(plans),
            "Professor": current_professor or nextfit_professor,
            "Plano": _join_unicos(plans),
            "Modalidade": _join_unicos(modalities_by_client.get(client_id, [])),
            "Status": "ATIVO" if _is_active_client(client, active_contract_clients) else "INATIVO",
            "AtualizadoEm": now_iso,
        })

    rows.sort(key=lambda row: (row["Status"] != "ATIVO", _norm(row["Nome"])))
    return rows


def sync_once() -> dict[str, Any]:
    load_dotenv()
    if not postgres_data.enabled():
        raise RuntimeError("DATABASE_URL nao configurada.")

    rows = build_portal_rows(
        clients=postgres_data.read_raw_table("nf_clientes"),
        users=postgres_data.read_raw_table("nf_usuarios"),
        contracts=postgres_data.read_raw_table("nf_contratos_cliente"),
        contract_bases=postgres_data.read_raw_table("nf_contratos_base"),
        existing_rows=postgres_data.read_alunos(),
        now_iso=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    written = postgres_data.replace_portal_alunos(rows)
    return {
        "rows": written,
        "ativos": sum(1 for row in rows if row["Status"] == "ATIVO"),
        "com_professor": sum(1 for row in rows if row["Status"] == "ATIVO" and row["Professor"]),
        "com_turno": sum(1 for row in rows if row["Turno"]),
    }


def main() -> int:
    try:
        summary = sync_once()
    except Exception as exc:
        print(f"[erro] sync_portal_alunos falhou: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
