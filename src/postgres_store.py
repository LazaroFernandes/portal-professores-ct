from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


TIMEZONE = ZoneInfo("America/Sao_Paulo")


def now_sp() -> datetime:
    return datetime.now(TIMEZONE)


def connect():
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL nao configurada.")
    import psycopg

    return psycopg.connect(database_url)


def record_key(record: dict[str, Any], key_fields: tuple[str, ...]) -> str:
    for field in key_fields:
        value = record.get(field)
        if value not in (None, ""):
            return str(value)
    body = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def safe_table_name(prefix: str, raw: str) -> str:
    text = unicodedata.normalize("NFD", raw)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    if not text:
        text = "sem_nome"
    if text[0].isdigit():
        text = "_" + text
    return f"{prefix}_{text}"[:63]


def create_run_tables(conn) -> None:
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
    conn.commit()


def start_run(conn, source: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sync_runs (started_at, status, source, details)
            VALUES (%s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (now_sp(), "running", source, "{}"),
        )
        row = cur.fetchone()
    conn.commit()
    return int(row[0])


def finish_run(conn, run_id: int, status: str, details: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE sync_runs
            SET finished_at = %s, status = %s, details = %s::jsonb
            WHERE id = %s
            """,
            (now_sp(), status, json.dumps(details, ensure_ascii=False), run_id),
        )
    conn.commit()


def record_error(conn, run_id: int, endpoint: str, exc: Exception) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sync_errors (run_id, endpoint, message)
            VALUES (%s, %s, %s)
            """,
            (run_id, endpoint, str(exc)[:2000]),
        )
    conn.commit()


def create_raw_table(conn, table: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
                external_id TEXT PRIMARY KEY,
                payload JSONB NOT NULL,
                fetched_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cur.execute(f"CREATE INDEX IF NOT EXISTS {table}_payload_gin ON {table} USING GIN (payload)")
    conn.commit()


def upsert_raw_records(
    conn,
    table: str,
    records: list[dict[str, Any]],
    key_fields: tuple[str, ...],
) -> int:
    if not records:
        return 0
    from psycopg.types.json import Jsonb

    create_raw_table(conn, table)
    fetched_at = now_sp()
    rows = [(record_key(record, key_fields), Jsonb(record), fetched_at) for record in records]
    with conn.cursor() as cur:
        cur.executemany(
            f"""
            INSERT INTO {table} (external_id, payload, fetched_at, updated_at)
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
