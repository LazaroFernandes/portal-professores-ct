"""Read-only weekly analysis, grouped by the current active portfolio."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from controle_professores import postgres_data
from controle_professores.client import open_controle
from controle_professores.config import TAB_ALUNOS, TAB_REGISTRO
from .nextfit_roster import current_roster


TIMEZONE = ZoneInfo("America/Sao_Paulo")


def read_source() -> tuple[list[dict], list[dict], str]:
    students = current_roster()["students"]
    if not postgres_data.enabled():
        sheet = open_controle()
        return students, sheet.read_tab_all(TAB_REGISTRO), "API NextFit + registros Google Sheets"
    # Unlike the legacy readers, analytics must never create or seed tables.
    with postgres_data._connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            if not all(postgres_data._table_exists(conn, table) for table in (
                "portal_registro_semanal",
            )):
                raise RuntimeError("Base de acompanhamento ainda não disponível")
            cur.execute("SELECT payload FROM portal_registro_semanal ORDER BY semana_inicio, cliente_id")
            records = [dict(row["payload"] or {}) for row in cur.fetchall()]
    return students, records, "API NextFit + registros PostgreSQL"


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _client_id(row: dict) -> int | None:
    try:
        value = int(row["ClienteId"])
        return value if value > 0 else None
    except (KeyError, ValueError, TypeError):
        return None


def _counts(items: list[dict]) -> dict:
    total = len(items)
    complete = sum(item["status"] == "complete" for item in items)
    partial = sum(item["status"] == "partial" for item in items)
    filled = complete + partial
    return {
        "total": total, "filled": filled, "complete": complete, "partial": partial,
        "empty": total - filled, "pending": total - complete,
        "filled_pct": round(100 * filled / total, 1) if total else 0,
        "complete_pct": round(100 * complete / total, 1) if total else 0,
    }


def weekly_analysis(start: date | None = None) -> dict:
    now = datetime.now(TIMEZONE)
    selected = start or now.date()
    monday = selected - timedelta(days=selected.weekday())
    week = monday.isoformat()
    students, records, source = read_source()
    roster = {}
    invalid_students = duplicate_students = 0
    for row in students:
        client_id = _client_id(row)
        if client_id is None:
            invalid_students += 1
            continue
        duplicate_students += client_id in roster
        roster[client_id] = row

    active = {key: row for key, row in roster.items() if _text(row.get("Status")).upper() == "ATIVO"}
    index = {}
    available_weeks = set()
    duplicate_records = 0
    for row in records:
        try:
            recorded_week = date.fromisoformat(_text(row.get("SemanaInicio")))
            if recorded_week.weekday() == 0:
                available_weeks.add(recorded_week.isoformat())
        except ValueError:
            pass
        if _text(row.get("SemanaInicio")) != week:
            continue
        client_id = _client_id(row)
        if client_id is None:
            continue
        existing = index.get(client_id)
        if existing is not None:
            duplicate_records += 1
            current_professor = _text(active.get(client_id, {}).get("Professor")).casefold()
            # Timestamp first; ties prefer the current portfolio, then source order.
            def priority(record):
                return (_text(record.get("AtualizadoEm")),
                        _text(record.get("Professor")).casefold() == current_professor)
            if priority(existing) > priority(row):
                continue
        index[client_id] = row

    items = []
    for client_id, row in active.items():
        record = index.get(client_id, {})
        frequency, performance, report = (_text(record.get(field)) for field in (
            "Frequencia", "Desempenho", "Relato",
        ))
        filled = sum(bool(value) for value in (frequency, performance, report))
        items.append({
            "client_id": client_id, "name": _text(row.get("Nome")),
            "professor": _text(row.get("Professor")), "shift": _text(row.get("Turno")),
            "modality": _text(row.get("Modalidade")), "plan": _text(row.get("Plano")),
            "frequency": frequency, "performance": performance, "report": report,
            "status": "complete" if filled == 3 else "partial" if filled else "empty",
            "record_exists": client_id in index,
            "record_professor": _text(record.get("Professor")),
            "updated_at": _text(record.get("AtualizadoEm")),
        })
    items.sort(key=lambda item: (item["name"].casefold(), item["client_id"]))
    groups = defaultdict(list)
    for item in items:
        groups[item["professor"]].append(item)
    professors = [{"name": name, **_counts(group)} for name, group in groups.items()]
    professors.sort(key=lambda item: (item["filled_pct"], item["name"].casefold()))
    return {
        "start": week, "end": (monday + timedelta(days=6)).isoformat(),
        "current_start": (now.date() - timedelta(days=now.weekday())).isoformat(),
        "read_at": now.isoformat(), "source": source,
        "available_weeks": sorted(available_weeks, reverse=True),
        "summary": {**_counts(items), "professors": sum(bool(name) for name in groups),
                    "unassigned": len(groups.get("", [])),
                    "not_opened": sum(not item["record_exists"] for item in items)},
        "professors": professors, "students": items,
        "quality": {"invalid_students": invalid_students, "duplicate_students": duplicate_students,
                    "duplicate_records": duplicate_records,
                    "records_outside_current_portfolio": len(set(index) - set(active))},
    }
