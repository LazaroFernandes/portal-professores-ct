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
from google.oauth2.service_account import Credentials
import gspread

from postgres_store import (
    connect,
    create_run_tables,
    finish_run,
    record_error,
    safe_table_name,
    start_run,
)


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
logger = logging.getLogger("nextfit.sheets_import")


@dataclass(frozen=True)
class SheetSource:
    name: str
    env_var: str
    table_prefix: str


SOURCES: tuple[SheetSource, ...] = (
    SheetSource("nextfit", "GOOGLE_SHEET_ID", "sheet_nextfit"),
    SheetSource("controle", "CONTROLE_PROFESSORES_SHEET_ID", "sheet_controle"),
)


def _credentials() -> Credentials:
    load_dotenv()
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw:
        try:
            info = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON contem JSON invalido") from exc
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    path = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials/service-account.json").strip()
    return Credentials.from_service_account_file(path, scopes=SCOPES)


def _open_sheet(source: SheetSource):
    sheet_id = os.environ.get(source.env_var, "").strip()
    if not sheet_id:
        raise RuntimeError(f"{source.env_var} nao configurada.")
    client = gspread.authorize(_credentials())
    return client.open_by_key(sheet_id)


def _rows_from_worksheet(worksheet) -> list[dict[str, Any]]:
    values = worksheet.get_all_values()
    if not values:
        return []
    headers = [str(value or "").strip() or f"coluna_{index + 1}" for index, value in enumerate(values[0])]
    rows: list[dict[str, Any]] = []
    for row_number, values_row in enumerate(values[1:], start=2):
        payload = {
            header: values_row[index] if index < len(values_row) else ""
            for index, header in enumerate(headers)
        }
        payload["_sheet_row_number"] = row_number
        rows.append(payload)
    return rows


def _replace_table(conn, table: str, rows: list[dict[str, Any]], source_name: str, worksheet: str) -> int:
    from psycopg.types.json import Jsonb

    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
                row_number INTEGER PRIMARY KEY,
                source_name TEXT NOT NULL,
                worksheet_name TEXT NOT NULL,
                payload JSONB NOT NULL,
                imported_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cur.execute(f"CREATE INDEX IF NOT EXISTS {table}_payload_gin ON {table} USING GIN (payload)")
        cur.execute(f"TRUNCATE TABLE {table}")
        if rows:
            cur.executemany(
                f"""
                INSERT INTO {table} (row_number, source_name, worksheet_name, payload, imported_at)
                VALUES (%s, %s, %s, %s, now())
                """,
                [
                    (int(row["_sheet_row_number"]), source_name, worksheet, Jsonb(row))
                    for row in rows
                ],
            )
    conn.commit()
    return len(rows)


def import_once(selected_sources: set[str] | None = None) -> dict[str, Any]:
    load_dotenv()
    started = perf_counter()
    summary: dict[str, Any] = {"sources": {}, "errors": 0}
    with connect() as conn:
        create_run_tables(conn)
        run_id = start_run(conn, "google-sheets-import")
        try:
            for source in SOURCES:
                if selected_sources and source.name not in selected_sources:
                    continue
                logger.info("Importando planilha %s", source.name)
                try:
                    spreadsheet = _open_sheet(source)
                    source_summary: dict[str, int] = {}
                    for worksheet in spreadsheet.worksheets():
                        table = safe_table_name(source.table_prefix, worksheet.title)
                        rows = _rows_from_worksheet(worksheet)
                        source_summary[worksheet.title] = _replace_table(
                            conn, table, rows, source.name, worksheet.title
                        )
                    summary["sources"][source.name] = source_summary
                except Exception as exc:
                    summary["errors"] += 1
                    summary["sources"][source.name] = {"error": str(exc)}
                    record_error(conn, run_id, f"sheets:{source.name}", exc)
                    logger.exception("Falha ao importar planilha %s", source.name)
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
    parser = argparse.ArgumentParser(description="Importa abas do Google Sheets para PostgreSQL.")
    parser.add_argument(
        "--source",
        action="append",
        choices=[source.name for source in SOURCES],
        help="Importa apenas uma planilha: nextfit ou controle. Pode repetir.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format=LOG_FORMAT)
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    selected = set(args.source) if args.source else None
    try:
        summary = import_once(selected)
    except Exception:
        logger.exception("Importacao Google Sheets falhou")
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
