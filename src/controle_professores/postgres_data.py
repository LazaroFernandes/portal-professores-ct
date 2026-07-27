from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

from controle_professores.config import HEADERS_ALUNOS, HEADERS_CONFIG, HEADERS_REGISTRO
from controle_professores.semana import fmt_iso, semana_de


def enabled() -> bool:
    return bool(os.environ.get("DATABASE_URL", "").strip())


def _connect():
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL nao configurada.")
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(database_url, row_factory=dict_row)


def _jsonb(value: dict[str, Any]):
    from psycopg.types.json import Jsonb

    return Jsonb(value)


def _agora_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _clean_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in row.items() if key != "_sheet_row_number"}


def _table_exists(conn, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL AS exists", (table,))
        row = cur.fetchone()
    return bool(row and row["exists"])


def _sheet_payloads(conn, table: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, table):
        return []
    with conn.cursor() as cur:
        cur.execute(f"SELECT payload FROM {table} ORDER BY row_number")
        return [_clean_payload(dict(row["payload"] or {})) for row in cur.fetchall()]


def read_raw_table(table: str) -> list[dict[str, Any]]:
    with _connect() as conn:
        if not _table_exists(conn, table):
            return []
        with conn.cursor() as cur:
            cur.execute(f"SELECT payload FROM {table} ORDER BY external_id")
            return [dict(row["payload"] or {}) for row in cur.fetchall()]


def _ensure_portal_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS portal_alunos (
                cliente_id BIGINT PRIMARY KEY,
                payload JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS portal_registro_semanal (
                cliente_id BIGINT NOT NULL,
                semana_inicio TEXT NOT NULL,
                payload JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (cliente_id, semana_inicio)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS portal_config (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    conn.commit()
    _seed_portal_tables(conn)


def _seed_portal_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) AS total FROM portal_alunos")
        alunos_total = int(cur.fetchone()["total"])
    if alunos_total == 0:
        alunos = _sheet_payloads(conn, "sheet_controle_alunos")
        rows = []
        for aluno in alunos:
            try:
                cliente_id = int(aluno.get("ClienteId"))
            except (TypeError, ValueError):
                continue
            rows.append((cliente_id, _jsonb({header: aluno.get(header, "") for header in HEADERS_ALUNOS})))
        if rows:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO portal_alunos (cliente_id, payload)
                    VALUES (%s, %s)
                    ON CONFLICT (cliente_id) DO NOTHING
                    """,
                    rows,
                )
            conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) AS total FROM portal_registro_semanal")
        registros_total = int(cur.fetchone()["total"])
    if registros_total == 0:
        registros = _sheet_payloads(conn, "sheet_controle_registrosemanal")
        rows = []
        for registro in registros:
            try:
                cliente_id = int(registro.get("ClienteId"))
            except (TypeError, ValueError):
                continue
            semana_inicio = str(registro.get("SemanaInicio") or "").strip()
            if not semana_inicio:
                continue
            rows.append((
                cliente_id,
                semana_inicio,
                _jsonb({header: registro.get(header, "") for header in HEADERS_REGISTRO}),
            ))
        if rows:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO portal_registro_semanal (cliente_id, semana_inicio, payload)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (cliente_id, semana_inicio) DO NOTHING
                    """,
                    rows,
                )
            conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) AS total FROM portal_config")
        config_total = int(cur.fetchone()["total"])
    if config_total == 0:
        configs = _sheet_payloads(conn, "sheet_controle_config")
        rows = [
            (str(row.get("Chave") or "").strip(), str(row.get("Valor") or "").strip())
            for row in configs
            if str(row.get("Chave") or "").strip()
        ]
        if rows:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO portal_config (chave, valor)
                    VALUES (%s, %s)
                    ON CONFLICT (chave) DO NOTHING
                    """,
                    rows,
                )
            conn.commit()


def read_alunos() -> list[dict[str, Any]]:
    with _connect() as conn:
        _ensure_portal_tables(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT payload FROM portal_alunos ORDER BY payload->>'Nome'")
            return [dict(row["payload"] or {}) for row in cur.fetchall()]


def read_registros() -> list[dict[str, Any]]:
    with _connect() as conn:
        _ensure_portal_tables(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT payload FROM portal_registro_semanal ORDER BY semana_inicio, payload->>'Nome'")
            return [dict(row["payload"] or {}) for row in cur.fetchall()]


def set_turno(cliente_id: int, turno: str) -> str:
    with _connect() as conn:
        _ensure_portal_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE portal_alunos
                SET payload = jsonb_set(payload, '{Turno}', to_jsonb(%s::text), true),
                    updated_at = now()
                WHERE cliente_id = %s
                """,
                (turno, cliente_id),
            )
            updated = cur.rowcount
        conn.commit()
    return "updated" if updated else "not_found"


def open_week(inicio: date, professor_filtro: str | None = None) -> tuple[int, int]:
    ini, fim = semana_de(inicio)
    alunos = read_alunos()
    ativos = [row for row in alunos if str(row.get("Status") or "").strip().upper() == "ATIVO"]
    if professor_filtro:
        ativos = [row for row in ativos if str(row.get("Professor") or "").strip() == professor_filtro]

    semana_inicio = fmt_iso(ini)
    semana_fim = fmt_iso(fim)
    rows = []
    for aluno in ativos:
        try:
            cliente_id = int(aluno.get("ClienteId"))
        except (TypeError, ValueError):
            continue
        payload = {header: "" for header in HEADERS_REGISTRO}
        payload.update({
            "ClienteId": cliente_id,
            "Nome": aluno.get("Nome", ""),
            "Professor": aluno.get("Professor", ""),
            "SemanaInicio": semana_inicio,
            "SemanaFim": semana_fim,
        })
        rows.append((cliente_id, semana_inicio, _jsonb(payload)))

    inserted = 0
    with _connect() as conn:
        _ensure_portal_tables(conn)
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO portal_registro_semanal (cliente_id, semana_inicio, payload)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (cliente_id, semana_inicio) DO NOTHING
                    """,
                    row,
                )
                inserted += cur.rowcount
        conn.commit()
    return len(ativos), inserted


def upsert_registros(items: list[dict[str, Any]]) -> tuple[int, int]:
    updated = 0
    inserted = 0
    agora = _agora_iso()
    with _connect() as conn:
        _ensure_portal_tables(conn)
        with conn.cursor() as cur:
            for item in items:
                try:
                    cliente_id = int(item["ClienteId"])
                except (KeyError, TypeError, ValueError):
                    continue
                semana_inicio = str(item.get("SemanaInicio") or "").strip()
                if not semana_inicio:
                    continue
                payload = {header: "" for header in HEADERS_REGISTRO}
                payload.update({key: value for key, value in item.items() if key in HEADERS_REGISTRO})
                payload["ClienteId"] = cliente_id
                payload["AtualizadoEm"] = agora
                cur.execute(
                    """
                    INSERT INTO portal_registro_semanal (cliente_id, semana_inicio, payload, updated_at)
                    VALUES (%s, %s, %s, now())
                    ON CONFLICT (cliente_id, semana_inicio) DO UPDATE
                    SET payload = portal_registro_semanal.payload || EXCLUDED.payload,
                        updated_at = now()
                    RETURNING xmax = 0 AS inserted
                    """,
                    (cliente_id, semana_inicio, _jsonb(payload)),
                )
                row = cur.fetchone()
                if row and row["inserted"]:
                    inserted += 1
                else:
                    updated += 1
        conn.commit()
    return updated, inserted
