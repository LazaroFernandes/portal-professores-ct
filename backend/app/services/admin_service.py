from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date
from typing import Any

from controle_professores.client import get_config_int
from controle_professores.retencao import (
    alertas_sumico,
    alunos_recentes,
    carregar_tudo,
    comparativo_semana,
    historico_aluno,
    periodo_mes,
    queda_frequencia,
    retencao_comparativa,
    retencao_por_modalidade,
)
from controle_professores.semana import parse_iso
from controle_professores.treinos import carregar_execucoes, metricas_cohort

from ..core.cache import cache


def _base():
    return cache.get_or_set("admin:base", 180, carregar_tudo)


def _executions():
    return cache.get_or_set("admin:executions", 180, carregar_execucoes)


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items() if key != "cohort_ids" and key != "nome_por_cliente"}
    if isinstance(value, (list, tuple, set)):
        return [_plain(item) for item in value]
    if isinstance(value, (date,)):
        return value.isoformat()
    return value


def retention(year_a: int, month_a: int, year_b: int, month_b: int, target: int | None) -> dict:
    target = target or get_config_int("META_PRESENCAS_MES", 8)
    data = retencao_comparativa(year_a, month_a, year_b, month_b, _base(), target)
    start_b, end_b = periodo_mes(year_b, month_b)
    executions = _executions()
    lines = []
    for line in data["linhas_prof"]:
        plain = _plain(line)
        training = metricas_cohort(
            line.cohort_ids, start_b, end_b, executions, line.nome_por_cliente
        )
        plain["training"] = _plain(training)
        lines.append(plain)
    result = {key: _plain(value) for key, value in data.items() if key != "linhas_prof"}
    result["professors"] = lines
    return result


def modalities(year_a: int, month_a: int, year_b: int, month_b: int, group: str) -> dict:
    if group not in {"categoria", "plano"}:
        raise ValueError("Agrupamento inválido")
    return _plain(retencao_por_modalidade(year_a, month_a, year_b, month_b, _base(), group))


def attendance(days: int, mode: str) -> list[dict]:
    if not 1 <= days <= 60 or mode not in {"recent", "missing", "until"}:
        raise ValueError("Filtro de presença inválido")
    if mode == "recent":
        return alunos_recentes(_base(), days)
    return alertas_sumico(_base(), days, "min" if mode == "missing" else "max")


def decline(weeks: int) -> list[dict]:
    if not 2 <= weeks <= 8:
        raise ValueError("Número de semanas inválido")
    return queda_frequencia(_base(), weeks)


def weekly_comparison(start_raw: str) -> list[dict]:
    start = parse_iso(start_raw)
    if not start:
        raise ValueError("Semana inválida")
    return comparativo_semana(start, _base())


def student_history(client_id: int) -> dict:
    return historico_aluno(client_id, _base())


def student_options() -> list[dict]:
    output = []
    for row in _base().alunos:
        try:
            client_id = int(row.get("ClienteId"))
        except (TypeError, ValueError):
            continue
        output.append({
            "client_id": client_id,
            "name": str(row.get("Nome") or ""),
            "professor": str(row.get("Professor") or ""),
            "status": str(row.get("Status") or ""),
        })
    return sorted(output, key=lambda item: item["name"].casefold())
