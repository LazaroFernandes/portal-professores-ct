from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from nextfit_client import NextFitClient


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
TIMEZONE = ZoneInfo("America/Sao_Paulo")
logger = logging.getLogger("nextfit.sync")


@dataclass(frozen=True)
class Endpoint:
    name: str
    table: str
    method: str
    key_fields: tuple[str, ...]


ENDPOINTS: tuple[Endpoint, ...] = (
    Endpoint("clientes", "nf_clientes", "clientes", ("id", "codigo", "codigoCliente")),
    Endpoint("usuarios", "nf_usuarios", "usuarios", ("id", "codigo", "codigoUsuario")),
    Endpoint("contratos_base", "nf_contratos_base", "contratos_base", ("id", "codigo", "codigoContratoBase")),
    Endpoint("contratos_cliente", "nf_contratos_cliente", "contratos_cliente", ("id", "codigo", "codigoContrato", "codigoCliente")),
    Endpoint("contas_receber", "nf_contas_receber", "contas_receber", ("id", "codigo", "codigoContaReceber")),
    Endpoint("vendas", "nf_vendas", "vendas", ("id", "codigo", "codigoVenda")),
    Endpoint("movimentos_financeiros", "nf_movimentos_financeiros", "movimentos_financeiros", ("id", "codigo", "codigoMovimento")),
    Endpoint("oportunidades", "nf_oportunidades", "oportunidades", ("id", "codigo", "codigoOportunidade")),
    Endpoint("agenda", "nf_agenda", "agenda", ("id", "codigo", "codigoAgenda")),
)


def _now() -> datetime:
    return datetime.now(TIMEZONE)


def _record_key(record: dict[str, Any], key_fields: tuple[str, ...]) -> str:
    for field in key_fields:
        value = record.get(field)
        if value not in (None, ""):
            return str(value)
    body = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _client_from_env() -> NextFitClient:
    load_dotenv()
    api_key = os.environ.get("NEXTFIT_API_KEY", "").strip()
    base_url = os.environ.get("NEXTFIT_BASE_URL", "").strip()
    version = os.environ.get("NEXTFIT_API_VERSION", "1").strip() or "1"
    if not api_key:
        raise RuntimeError("NEXTFIT_API_KEY nao configurada.")
    if not base_url:
        raise RuntimeError("NEXTFIT_BASE_URL nao configurada.")
    return NextFitClient(api_key=api_key, base_url=base_url, version=version)


def _connect():
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL nao configurada.")
    import psycopg

    return psycopg.connect(database_url)


def _create_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_runs (
                id BIGSERIAL PRIMARY KEY,
                started_at TIMESTAMPTZ NOT NULL,
                finished_at TIMESTAMPTZ,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                details JSONB NOT NULL DEFAULT '{}'::jsonb
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_errors (
                id BIGSERIAL PRIMARY KEY,
                run_id BIGINT REFERENCES sync_runs(id) ON DELETE SET NULL,
                endpoint TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        for endpoint in ENDPOINTS:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {endpoint.table} (
                    external_id TEXT PRIMARY KEY,
                    payload JSONB NOT NULL,
                    fetched_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS {endpoint.table}_payload_gin ON {endpoint.table} USING GIN (payload)"
            )
    conn.commit()


def _start_run(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sync_runs (started_at, status, source, details)
            VALUES (%s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (_now(), "running", "nextfit-public-api", "{}"),
        )
        row = cur.fetchone()
    conn.commit()
    return int(row[0])


def _finish_run(conn, run_id: int, status: str, details: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE sync_runs
            SET finished_at = %s, status = %s, details = %s::jsonb
            WHERE id = %s
            """,
            (_now(), status, json.dumps(details, ensure_ascii=False), run_id),
        )
    conn.commit()


def _record_error(conn, run_id: int, endpoint: str, exc: Exception) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sync_errors (run_id, endpoint, message)
            VALUES (%s, %s, %s)
            """,
            (run_id, endpoint, str(exc)[:2000]),
        )
    conn.commit()


def _upsert_records(conn, endpoint: Endpoint, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    from psycopg.types.json import Jsonb

    fetched_at = _now()
    rows = [
        (_record_key(record, endpoint.key_fields), Jsonb(record), fetched_at)
        for record in records
    ]
    with conn.cursor() as cur:
        cur.executemany(
            f"""
            INSERT INTO {endpoint.table} (external_id, payload, fetched_at, updated_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (external_id) DO UPDATE
            SET payload = EXCLUDED.payload,
                fetched_at = EXCLUDED.fetched_at,
                updated_at = now()
            """,
            rows,
        )
    conn.commit()
    return len(rows)


def sync_once(selected: set[str] | None = None) -> dict[str, Any]:
    client = _client_from_env()
    started = perf_counter()
    summary: dict[str, Any] = {"endpoints": {}, "errors": 0}
    with _connect() as conn:
        _create_schema(conn)
        run_id = _start_run(conn)
        try:
            for endpoint in ENDPOINTS:
                if selected and endpoint.name not in selected:
                    continue
                logger.info("Sincronizando %s", endpoint.name)
                try:
                    fetch = getattr(client, endpoint.method)
                    records = fetch()
                    count = _upsert_records(conn, endpoint, records)
                    summary["endpoints"][endpoint.name] = count
                    logger.info("%s sincronizado: %s registros", endpoint.name, count)
                except Exception as exc:
                    summary["errors"] += 1
                    summary["endpoints"][endpoint.name] = {"error": str(exc)}
                    _record_error(conn, run_id, endpoint.name, exc)
                    logger.exception("Falha ao sincronizar %s", endpoint.name)
            status = "success" if summary["errors"] == 0 else "partial"
            summary["duration_seconds"] = round(perf_counter() - started, 2)
            _finish_run(conn, run_id, status, summary)
        except Exception as exc:
            summary["errors"] += 1
            summary["fatal_error"] = str(exc)
            _finish_run(conn, run_id, "failed", summary)
            raise
    return summary


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sincroniza dados publicos do NextFit para PostgreSQL.")
    parser.add_argument(
        "--endpoint",
        action="append",
        choices=[endpoint.name for endpoint in ENDPOINTS],
        help="Sincroniza apenas um endpoint. Pode ser usado mais de uma vez.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format=LOG_FORMAT)
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    selected = set(args.endpoint) if args.endpoint else None
    try:
        summary = sync_once(selected)
    except Exception:
        logger.exception("Sincronizacao NextFit falhou")
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
