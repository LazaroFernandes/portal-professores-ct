from __future__ import annotations

import unicodedata
from datetime import datetime

from controle_professores.client import open_nextfit_sync

from ..core.cache import cache


TABS = {
    "actions": "RetornoSemanal",
    "alerts": "Alerta7Dias",
    "renewals": "PipelineRenovacao",
    "without_professor": "SemProfessor",
    "onboarding": "Onboarding30d",
    "dates": "Datas",
    "contacts": "LogContatos",
    "metrics": "MetricasSemana",
}

MODALITY_RULES: list[tuple[str, list[str]]] = [
    ("ASSESSORIA SEMESTRAL", ["plano", "6 meses"]),
    ("ASSESSORIA SEMESTRAL", ["assessoria", "semestral"]),
    ("ASSESSORIA SEMESTRAL", ["acessoria", "semestral"]),
    ("ASSESSORIA FIXO", ["acessoria", "fixo"]),
    ("ASSESSORIA FIXO", ["assessoria", "fixo"]),
    ("CONSULTORIA TREINOS", ["consultoria", "treinos"]),
    ("CONSULTORIA CRIS", ["consultoria", "cris"]),
    ("CONSULTORIA ITALO", ["consultoria", "iv"]),
    ("CONSULTORIA LIVRE", ["consultoria", "livre"]),
    ("CONSULTORIA LIVRE", ["trimestral", "livre"]),
    ("CONSULTORIA LIVRE", ["plano semestral", "livre"]),
    ("CONSULTORIA", ["consultoria"]),
    ("PERSONAL CRIS", ["personal", "cris"]),
    ("PERSONAL ITALO", ["personal", "italo"]),
    ("PERSONAL ITALO", ["personal", "iv"]),
    ("PERSONAL EQUIPE", ["personal", "equipe"]),
    ("PERSONAL", ["personal"]),
    ("HYROX", ["hyrox"]),
    ("KIDS", ["kids"]),
    ("FATBURN", ["fatburn"]),
    ("PROJETO", ["projeto"]),
    ("QUADRA", ["quadra"]),
    ("PARCERIA", ["parceria"]),
    ("FUNCIONARIOS", ["funcionarios"]),
]


def categorize_modality(description: str) -> str:
    if not description:
        return "(sem contrato)"
    normalized = unicodedata.normalize("NFD", str(description))
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn").lower().strip()
    for category, terms in MODALITY_RULES:
        if all(term in normalized for term in terms):
            return category
    return "OUTROS"


def _rows(key: str) -> list[dict]:
    if key not in TABS:
        raise ValueError("Conjunto de dados inválido")
    ttl = 60 if key == "contacts" else 300
    return cache.get_or_set(
        f"crm:{key}", ttl, lambda: open_nextfit_sync().read_tab_all(TABS[key])
    )


def dashboard() -> dict:
    result = {}
    for key in TABS:
        rows = [dict(row) for row in _rows(key)]
        if key in {"actions", "alerts", "renewals", "without_professor", "onboarding"}:
            for row in rows:
                row["Modalidade"] = categorize_modality(str(row.get("Contrato") or ""))
        if key == "without_professor":
            rows = [row for row in rows if row.get("Modalidade") != "FUNCIONARIOS"]
        result[key] = rows
    return result


def add_contact(data) -> dict:
    row = {
        "DataContato": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "CodigoCliente": data.client_id,
        "NomeCliente": data.client_name,
        "Origem": data.source,
        "Status": data.status,
        "Observacao": data.notes,
        "Operador": data.operator,
    }
    open_nextfit_sync().append_tab(TABS["contacts"], [row])
    cache.invalidate("crm:contacts")
    return row
