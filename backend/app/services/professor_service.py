from __future__ import annotations

from datetime import date, timedelta

from controle_professores.abrir_semana import abrir_semana
from controle_professores.alunos import set_turno
from controle_professores.client import open_controle
from controle_professores.config import TAB_ALUNOS, TAB_REGISTRO
from controle_professores.registro import upsert_em_lote
from controle_professores.semana import fmt_iso, label_semana, parse_iso, semana_atual

from ..core.cache import cache


def _alunos() -> list[dict]:
    return cache.get_or_set("controle:alunos", 120, lambda: open_controle().read_tab_all(TAB_ALUNOS))


def _registros() -> list[dict]:
    return cache.get_or_set("controle:registros", 120, lambda: open_controle().read_tab_all(TAB_REGISTRO))


def professores_disponiveis() -> list[str]:
    return sorted({
        str(row.get("Professor") or "").strip()
        for row in _alunos()
        if str(row.get("Status") or "").strip().upper() == "ATIVO"
        and str(row.get("Professor") or "").strip()
    })


def resolve_professor(user: dict, requested: str | None) -> str:
    if user.get("role") == "professor":
        return str(user["name"])
    available = professores_disponiveis()
    selected = (requested or (available[0] if available else "")).strip()
    if selected not in available:
        raise ValueError("Professor inválido")
    return selected


def _students_for(professor: str) -> list[dict]:
    return sorted(
        [
            row for row in _alunos()
            if str(row.get("Status") or "").strip().upper() == "ATIVO"
            and str(row.get("Professor") or "").strip().casefold() == professor.casefold()
        ],
        key=lambda row: str(row.get("Nome") or "").casefold(),
    )


def _week_index(professor: str, start: date) -> dict[int, dict]:
    result: dict[int, dict] = {}
    key = fmt_iso(start)
    for row in _registros():
        if str(row.get("SemanaInicio") or "").strip() != key:
            continue
        try:
            client_id = int(row["ClienteId"])
        except (KeyError, TypeError, ValueError):
            continue
        existing = result.get(client_id)
        if existing and str(existing.get("Professor") or "").strip() == professor:
            continue
        result[client_id] = row
    return result


def week_payload(user: dict, requested_professor: str | None, start_raw: str | None) -> dict:
    professor = resolve_professor(user, requested_professor)
    start = parse_iso(start_raw or "") or semana_atual()[0]
    end = start + timedelta(days=6)
    students = _students_for(professor)
    records = _week_index(professor, start)
    items = []
    for student in students:
        try:
            client_id = int(student["ClienteId"])
        except (KeyError, TypeError, ValueError):
            continue
        record = records.get(client_id, {})
        frequency = "" if record.get("Frequencia") is None else str(record.get("Frequencia")).strip()
        performance = "" if record.get("Desempenho") is None else str(record.get("Desempenho")).strip()
        report = "" if record.get("Relato") is None else str(record.get("Relato")).strip()
        items.append({
            "client_id": client_id,
            "name": str(student.get("Nome") or ""),
            "shift": str(student.get("Turno") or "").strip(),
            "plan": str(student.get("Plano") or "").strip(),
            "modality": str(student.get("Modalidade") or "").strip(),
            "frequency": frequency,
            "performance": performance,
            "report": report,
            "completed": bool(frequency or performance or report),
        })
    completed = sum(1 for item in items if item["completed"])
    opened = any(item["client_id"] in records for item in items)
    return {
        "professor": professor,
        "professors": professores_disponiveis() if user.get("role") == "admin" else [professor],
        "start": fmt_iso(start),
        "end": fmt_iso(end),
        "label": label_semana(start, end),
        "current": start == semana_atual()[0],
        "opened": opened,
        "summary": {"total": len(items), "completed": completed, "pending": len(items) - completed},
        "students": items,
    }


def open_week(user: dict, requested_professor: str | None, start_raw: str) -> dict:
    professor = resolve_professor(user, requested_professor)
    start = parse_iso(start_raw)
    if not start:
        raise ValueError("Data inicial inválida")
    active, created = abrir_semana(start, professor_filtro=professor)
    cache.invalidate("controle:registros")
    return {"active": active, "created": created}


def update_student(
    user: dict,
    requested_professor: str | None,
    start_raw: str,
    client_id: int,
    data,
) -> dict:
    professor = resolve_professor(user, requested_professor)
    start = parse_iso(start_raw)
    if not start:
        raise ValueError("Data inicial inválida")
    student = next((row for row in _students_for(professor) if int(row.get("ClienteId") or 0) == client_id), None)
    if not student:
        raise PermissionError("Aluno não pertence à carteira do professor")
    end = start + timedelta(days=6)
    upsert_em_lote([{
        "ClienteId": client_id,
        "Nome": str(student.get("Nome") or ""),
        "Professor": professor,
        "SemanaInicio": fmt_iso(start),
        "SemanaFim": fmt_iso(end),
        "Frequencia": data.frequencia,
        "Desempenho": data.desempenho,
        "Relato": data.relato,
    }])
    shift_status = "unchanged"
    current_shift = str(student.get("Turno") or "").strip().upper()
    if data.turno != current_shift:
        shift_status = set_turno(client_id, data.turno)
    cache.invalidate("controle:alunos", "controle:registros")
    return {"saved": True, "shift_status": shift_status}
