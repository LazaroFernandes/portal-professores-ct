from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any

from dotenv import load_dotenv

from nextfit_client import NextFitClient
from nextfit_v2_client import NextFitV2Client, TokenExpiredError
from postgres_store import (
    connect,
    create_raw_table,
    create_run_tables,
    finish_run,
    record_error,
    start_run,
    upsert_raw_records,
)


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
logger = logging.getLogger("nextfit.v2_sync")


@dataclass(frozen=True)
class V2Endpoint:
    name: str
    table: str
    key_fields: tuple[str, ...]


ENDPOINTS: tuple[V2Endpoint, ...] = (
    V2Endpoint("presencas", "nf_v2_presencas", ("Id", "id", "Codigo", "codigo")),
    V2Endpoint("treinos", "nf_v2_treinos", ("TreinoId", "Id", "id")),
)


def _resolve_presencas_window() -> tuple[datetime, datetime]:
    data_final = datetime.now(tz=timezone.utc)
    raw_inicio = os.getenv("NEXTFIT_PRESENCAS_DATA_INICIAL", "").strip()
    if raw_inicio:
        try:
            return datetime.strptime(raw_inicio, "%Y-%m-%d").replace(tzinfo=timezone.utc), data_final
        except ValueError:
            logger.warning("NEXTFIT_PRESENCAS_DATA_INICIAL invalida: %s", raw_inicio)
    dias = int(os.getenv("NEXTFIT_PRESENCAS_DIAS", "30").strip() or "30")
    return data_final - timedelta(days=dias), data_final


def _public_client_from_env() -> NextFitClient:
    api_key = os.environ.get("NEXTFIT_API_KEY", "").strip()
    base_url = os.environ.get("NEXTFIT_BASE_URL", "").strip()
    version = os.environ.get("NEXTFIT_API_VERSION", "1").strip() or "1"
    if not api_key or not base_url:
        raise RuntimeError("NEXTFIT_API_KEY/NEXTFIT_BASE_URL nao configuradas.")
    return NextFitClient(api_key=api_key, base_url=base_url, version=version)


def _v2_client_from_env() -> NextFitV2Client:
    token = os.environ.get("NEXTFIT_V2_TOKEN", "").strip()
    refresh_token = os.environ.get("NEXTFIT_V2_REFRESH_TOKEN", "").strip() or None
    codigo_unidade = os.environ.get("NEXTFIT_CODIGO_UNIDADE", "").strip()
    if not token:
        raise RuntimeError("NEXTFIT_V2_TOKEN nao configurado.")
    if not codigo_unidade:
        raise RuntimeError("NEXTFIT_CODIGO_UNIDADE nao configurado.")
    return NextFitV2Client(
        token=token,
        refresh_token=refresh_token,
        codigo_unidade=codigo_unidade,
        env_path=None,
    )


def _active_clients(public_client: NextFitClient) -> set[int]:
    contratos = public_client.contratos_cliente()
    return {
        int(contract["codigoCliente"])
        for contract in contratos
        if contract.get("status") == "Ativo" and contract.get("codigoCliente") is not None
    }


def _fetch(endpoint: V2Endpoint, public_client: NextFitClient, v2_client: NextFitV2Client) -> list[dict[str, Any]]:
    if endpoint.name == "presencas":
        data_inicial, data_final = _resolve_presencas_window()
        return v2_client.presencas(data_inicial, data_final)
    if endpoint.name == "treinos":
        return v2_client.treinos_completos(clientes_ativos=_active_clients(public_client))
    raise RuntimeError(f"Endpoint v2 desconhecido: {endpoint.name}")


def sync_once(selected: set[str] | None = None) -> dict[str, Any]:
    load_dotenv()
    public_client = _public_client_from_env()
    v2_client = _v2_client_from_env()
    started = perf_counter()
    summary: dict[str, Any] = {"endpoints": {}, "errors": 0}
    with connect() as conn:
        create_run_tables(conn)
        for endpoint in ENDPOINTS:
            create_raw_table(conn, endpoint.table)
        run_id = start_run(conn, "nextfit-v2-api")
        try:
            for endpoint in ENDPOINTS:
                if selected and endpoint.name not in selected:
                    continue
                logger.info("Sincronizando V2 %s", endpoint.name)
                try:
                    records = _fetch(endpoint, public_client, v2_client)
                    count = upsert_raw_records(conn, endpoint.table, records, endpoint.key_fields)
                    summary["endpoints"][endpoint.name] = count
                    logger.info("V2 %s sincronizado: %s registros", endpoint.name, count)
                except TokenExpiredError as exc:
                    summary["errors"] += 1
                    summary["endpoints"][endpoint.name] = {"error": "token_expired"}
                    record_error(conn, run_id, f"v2:{endpoint.name}", exc)
                    logger.error("Token V2 expirado ao sincronizar %s", endpoint.name)
                    break
                except Exception as exc:
                    summary["errors"] += 1
                    summary["endpoints"][endpoint.name] = {"error": str(exc)}
                    record_error(conn, run_id, f"v2:{endpoint.name}", exc)
                    logger.exception("Falha ao sincronizar V2 %s", endpoint.name)
            status = "success" if summary["errors"] == 0 else "partial"
            summary["duration_seconds"] = round(perf_counter() - started, 2)
            finish_run(conn, run_id, status, summary)
        except Exception as exc:
            summary["errors"] += 1
            summary["fatal_error"] = str(exc)
            finish_run(conn, run_id, "failed", summary)
            raise
    return summary


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sincroniza dados NextFit V2 para PostgreSQL.")
    parser.add_argument(
        "--endpoint",
        action="append",
        choices=[endpoint.name for endpoint in ENDPOINTS],
        help="Sincroniza apenas um endpoint V2. Pode repetir.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format=LOG_FORMAT)
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    selected = set(args.endpoint) if args.endpoint else None
    try:
        summary = sync_once(selected)
    except Exception:
        logger.exception("Sincronizacao NextFit V2 falhou")
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
