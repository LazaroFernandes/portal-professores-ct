from __future__ import annotations

import subprocess
import sys
import threading
import uuid
from datetime import date, timedelta

from controle_professores.client import open_controle
from controle_professores.config import TAB_TAREFAS
from ..core.cache import cache
from ..core.config import PROJECT_ROOT


SNAPSHOT = PROJECT_ROOT / "scripts" / "_painel_segunda.json"
ORCHESTRATOR = PROJECT_ROOT / "scripts" / "painel_segunda.py"
HIDDEN_WITHOUT_PROFESSOR = {"FUNCIONARIOS"}
_task_lock = threading.RLock()


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _save_tasks(data: dict) -> None:
    rows = [
        {
            "Semana": data["week"],
            "Tipo": "auto",
            "TarefaId": task_id,
            "Texto": "",
            "Concluida": done,
        }
        for task_id, done in data["auto"].items()
    ]
    rows.extend(
        {
            "Semana": data["week"],
            "Tipo": "manual",
            "TarefaId": item["id"],
            "Texto": item["text"],
            "Concluida": item.get("done", False),
        }
        for item in data["manual"]
    )
    open_controle().write_tab(TAB_TAREFAS, rows)


def _as_bool(value: object) -> bool:
    return value is True or str(value).strip().lower() in {"true", "verdadeiro", "1", "sim"}


def load_tasks() -> dict:
    week = _monday(date.today()).isoformat()
    data = {"week": week, "auto": {}, "manual": []}
    with _task_lock:
        rows = open_controle().read_tab_all(TAB_TAREFAS)
        stored_week = str(rows[0].get("Semana") or week) if rows else week
        data["week"] = stored_week
        for row in rows:
            task_id = str(row.get("TarefaId") or "").strip()
            if not task_id:
                continue
            if str(row.get("Tipo") or "").strip().lower() == "auto":
                data["auto"][task_id] = _as_bool(row.get("Concluida"))
            else:
                data["manual"].append(
                    {
                        "id": task_id,
                        "text": str(row.get("Texto") or "").strip(),
                        "done": _as_bool(row.get("Concluida")),
                    }
                )
        if data["week"] != week:
            pending = [item for item in data["manual"] if not item.get("done")]
            data = {"week": week, "auto": {}, "manual": pending}
            _save_tasks(data)
    return data


def load_snapshot() -> dict:
    if not SNAPSHOT.exists():
        return {"available": False, "tasks": load_tasks(), "auto_tasks": []}
    snapshot = cache.get_or_set(
        "monday:snapshot", 30, lambda: json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    )
    return {
        "available": True,
        "snapshot": snapshot,
        "tasks": load_tasks(),
        "auto_tasks": auto_tasks(snapshot),
    }


def auto_tasks(snapshot: dict) -> list[dict]:
    today = snapshot.get("ligar_hoje", {})
    financial = snapshot.get("financeiro", {})
    items: list[tuple[str, str]] = []
    rules = [
        ("ligar_30d", len(today.get("sem_vir_30d", [])), "Ligar para {n} alunos sem vir há 30+ dias"),
        ("queda", len(today.get("sem_vir_7d_queda", [])), "Reengajar {n} alunos com queda de frequência"),
        ("renovar", len(today.get("vencendo_7d_acao", [])), "Renovar {n} contratos vencendo esta semana"),
        ("novos", len(snapshot.get("novos_reativados", [])), "Acompanhar {n} novos e reativados"),
        ("winback", len(snapshot.get("churn_60d", [])), "Revisar {n} perdas para win-back"),
    ]
    for key, count, label in rules:
        if count:
            items.append((key, label.format(n=count)))
    without = [
        item for item in snapshot.get("sem_professor", [])
        if item.get("modalidade") not in {"HYROX", "KIDS"}
        and item.get("modalidade") not in HIDDEN_WITHOUT_PROFESSOR
    ]
    if without:
        items.append(("sem_prof", f"Atribuir professor a {len(without)} alunos"))
    overdue = float(financial.get("receber_vencido") or 0)
    if overdue > 0:
        items.append(("receber", f"Cobrar R$ {overdue:,.2f} em recebimentos vencidos"))
    return [{"id": key, "text": label} for key, label in items]


def toggle_auto(task_id: str, done: bool) -> dict:
    with _task_lock:
        data = load_tasks()
        data["auto"][task_id] = done
        _save_tasks(data)
    return data


def add_manual(text: str) -> dict:
    with _task_lock:
        data = load_tasks()
        data["manual"].append({"id": uuid.uuid4().hex[:8], "text": text.strip(), "done": False})
        _save_tasks(data)
    return data


def toggle_manual(task_id: str, done: bool) -> dict:
    with _task_lock:
        data = load_tasks()
        item = next((item for item in data["manual"] if item.get("id") == task_id), None)
        if not item:
            raise ValueError("Tarefa não encontrada")
        item["done"] = done
        _save_tasks(data)
    return data


def delete_manual(task_id: str) -> dict:
    with _task_lock:
        data = load_tasks()
        before = len(data["manual"])
        data["manual"] = [item for item in data["manual"] if item.get("id") != task_id]
        if len(data["manual"]) == before:
            raise ValueError("Tarefa não encontrada")
        _save_tasks(data)
    return data


def refresh_snapshot() -> dict:
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(ORCHESTRATOR)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=15 * 60,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Falha ao gerar snapshot")[-1500:]
        raise RuntimeError(detail)
    cache.invalidate("monday:snapshot")
    return load_snapshot()
