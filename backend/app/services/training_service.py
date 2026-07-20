from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime

from controle_professores.client import open_nextfit_sync

from ..core.cache import cache


IGNORED_GROUPS = {"OBSERVAÇÕES", "OBSERVACOES"}


def _rows(tab: str) -> list[dict]:
    return cache.get_or_set(
        f"training:{tab}", 300, lambda: open_nextfit_sync().read_tab_all(tab)
    )


def parse_load(value) -> float | None:
    text = str(value or "")
    numbers = [float(item.replace(",", ".")) for item in re.findall(r"\d+(?:[.,]\d+)?", text)]
    positives = [number for number in numbers if number > 0]
    return max(positives) if positives else None


def real_sets(series, repetitions) -> int:
    try:
        count = int(series) if series not in (None, "") else 0
    except (TypeError, ValueError):
        count = 0
    if count == 4 and not re.search(r"[1-9]", str(repetitions or "")):
        return 3
    return count


def students() -> list[dict]:
    found: dict[int, str] = {}
    for row in _rows("Treinos"):
        try:
            client_id = int(row.get("CodigoCliente"))
        except (TypeError, ValueError):
            continue
        found[client_id] = str(row.get("NomeCliente") or f"#{client_id}")
    return [{"client_id": key, "name": value} for key, value in sorted(found.items(), key=lambda item: item[1].casefold())]


def student_detail(client_id: int) -> dict:
    workouts = [dict(row) for row in _rows("Treinos") if str(row.get("CodigoCliente")) == str(client_id)]
    executions = [dict(row) for row in _rows("HistoricoExecucoes") if str(row.get("CodigoCliente")) == str(client_id)]
    sessions: dict[str, list[dict]] = defaultdict(list)
    volume: dict[str, dict] = defaultdict(lambda: {"exercises": 0, "sets": 0})
    for row in workouts:
        session = str(row.get("Sessao") or "-")
        sessions[session].append(row)
        group = str(row.get("GrupoMuscular") or "").strip()
        if group and group.upper() not in IGNORED_GROUPS:
            volume[group]["exercises"] += 1
            volume[group]["sets"] += real_sets(row.get("Series"), row.get("Repeticoes"))
    for values in sessions.values():
        values.sort(key=lambda row: _numeric_order(row.get("OrdemExercicio")))
    histories: dict[str, list[dict]] = defaultdict(list)
    for row in executions:
        key = f"{row.get('Sessao') or '-'}::{row.get('Exercicio') or ''}"
        item = dict(row)
        item["CargaNum"] = parse_load(row.get("Carga"))
        item["DataExecucao"] = row.get("TimestampExecucao") or row.get("DataCaptura") or ""
        histories[key].append(item)
    for values in histories.values():
        values.sort(key=lambda row: str(row.get("DataExecucao") or ""))
    return {
        "client_id": client_id,
        "name": str(workouts[0].get("NomeCliente") or "") if workouts else "",
        "sessions": [{"name": key, "exercises": value} for key, value in sorted(sessions.items())],
        "volume": [{"group": key, **value} for key, value in sorted(volume.items(), key=lambda item: -item[1]["sets"])],
        "total_sets": sum(item["sets"] for item in volume.values()),
        "histories": histories,
    }


def _numeric_order(value) -> tuple[int, str]:
    try:
        return int(value), ""
    except (TypeError, ValueError):
        return 99999, str(value or "")
