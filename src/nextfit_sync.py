from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from dotenv import load_dotenv

from nextfit_client import NextFitClient
from postgres_store import (
    connect,
    create_raw_table,
    create_run_tables,
    finish_run,
    record_error,
    record_key,
    start_run,
    upsert_raw_records,
)


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
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


def _record_key(record: dict[str, Any], key_fields: tuple[str, ...]) -> str:
    return record_key(record, key_fields)


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
    return connect()


def _create_schema(conn) -> None:
    create_run_tables(conn)
    for endpoint in ENDPOINTS:
        create_raw_table(conn, endpoint.table)


def _start_run(conn) -> int:
    return start_run(conn, "nextfit-public-api")


def _finish_run(conn, run_id: int, status: str, details: dict[str, Any]) -> None:
    finish_run(conn, run_id, status, details)


def _record_error(conn, run_id: int, endpoint: str, exc: Exception) -> None:
    record_error(conn, run_id, endpoint, exc)


def _upsert_records(conn, endpoint: Endpoint, records: list[dict[str, Any]]) -> int:
    return upsert_raw_records(conn, endpoint.table, records, endpoint.key_fields)


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
