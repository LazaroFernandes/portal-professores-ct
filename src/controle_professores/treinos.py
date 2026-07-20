"""Analise de treinos executados — usa a aba HistoricoExecucoes do sync NextFit.

Metricas:
- Sessoes finalizadas no mes (total + por aluno)
- Progressao de carga (subiu/igual/caiu) por (cliente, exercicio, sessao)
- Volume medio (series executadas)
- Top alunos (mais sessoes)
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from controle_professores.client import open_nextfit_sync


# Convencao da academia: quando Series=4 e Repeticoes=0, soh 3 series sao reais
SERIE_DEFAULT = 3
GRUPOS_IGNORAR = {"OBSERVACOES", "OBSERVAÇÕES"}


def carregar_execucoes() -> list[dict[str, Any]]:
    """Le aba HistoricoExecucoes — retorna [] se nao existir."""
    sc = open_nextfit_sync()
    return sc.read_tab_all("HistoricoExecucoes")


def parse_carga(valor) -> float | None:
    """Extrai a carga maxima de uma string tipo '20/20/22/0'.

    Zeros sao ignorados (representam series nao usadas).
    """
    if valor is None or valor == "":
        return None
    s = str(valor)
    if s.lower() in {"nan", "none"}:
        return None
    nums = [float(m.replace(",", ".")) for m in re.findall(r"\d+(?:[.,]\d+)?", s)]
    positivos = [n for n in nums if n > 0]
    if not positivos:
        return None
    return max(positivos)


def _to_int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _parse_data_execucao(row: dict) -> date | None:
    """Prioriza TimestampExecucao, cai pra DataCaptura."""
    ts = str(row.get("TimestampExecucao") or "").strip()
    if ts:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    dc = str(row.get("DataCaptura") or "").strip()
    if dc:
        try:
            return datetime.strptime(dc[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


def _series_reais(row: dict) -> int:
    """Series reais executadas — aplica convencao S=4,R=0 -> 3."""
    s = _to_int(row.get("Series")) or 0
    reps_str = str(row.get("Repeticoes") or "")
    tem_reps = bool(re.search(r"[1-9]", reps_str))
    if s == 4 and not tem_reps:
        return SERIE_DEFAULT
    return s


@dataclass
class MetricasTreinos:
    cohort_size: int
    alunos_com_execucao: int            # quantos alunos do cohort treinaram em M
    sessoes_finalizadas: int             # total de (cliente, treino, sessao, dia) distintos
    media_sessoes_por_aluno: float
    series_totais: int                   # soma series reais
    media_series_por_sessao: float
    exercicios_progrediram: int
    exercicios_iguais: int
    exercicios_regrediram: int
    top_alunos: list[dict]               # [{Nome, Sessoes, SeriesTotais}]
    pior_3: list[dict]                   # 3 alunos do cohort com menos sessoes (excluindo zerados)
    sem_treinar: list[dict]              # alunos do cohort com 0 sessoes


def metricas_cohort(
    cohort_ids: set[int],
    inicio: date,
    fim: date,
    execucoes: list[dict] | None = None,
    nome_por_cliente: dict[int, str] | None = None,
) -> MetricasTreinos:
    """Calcula metricas de treino do cohort no periodo [inicio, fim] inclusive."""
    execucoes = execucoes if execucoes is not None else carregar_execucoes()
    nome_por_cliente = nome_por_cliente or {}

    # Filtra execucoes do cohort no periodo
    rows_relevantes: list[dict] = []
    for r in execucoes:
        cid = _to_int(r.get("CodigoCliente"))
        if cid is None or cid not in cohort_ids:
            continue
        d = _parse_data_execucao(r)
        if d is None or not (inicio <= d <= fim):
            continue
        # Ignora linhas de "observacoes" (PERIODIZACAO etc) que nao sao exercicio
        grupo = (r.get("GrupoMuscular") or "").strip().upper()
        if grupo in GRUPOS_IGNORAR:
            continue
        rows_relevantes.append(r)

    # Sessoes finalizadas: tuplas distintas
    sessoes_set: set[tuple[int, int, int, str]] = set()
    series_por_aluno: dict[int, int] = defaultdict(int)
    sessoes_por_aluno: dict[int, set] = defaultdict(set)

    # Para progressao de carga: para cada (cliente, exercicio, sessao) coleta lista [(data, carga)]
    progressao: dict[tuple[int, str, int], list[tuple[date, float]]] = defaultdict(list)

    for r in rows_relevantes:
        cid = int(r["CodigoCliente"])
        treino = _to_int(r.get("TreinoId")) or 0
        sessao = _to_int(r.get("Sessao")) or 0
        data = _parse_data_execucao(r)
        if data is None:
            continue

        chave_sessao = (cid, treino, sessao, data.isoformat())
        sessoes_set.add(chave_sessao)
        sessoes_por_aluno[cid].add(chave_sessao)
        series_por_aluno[cid] += _series_reais(r)

        ex_nome = (r.get("Exercicio") or "").strip()
        if not ex_nome:
            continue
        carga = parse_carga(r.get("Carga"))
        if carga is None:
            continue
        progressao[(cid, ex_nome, sessao)].append((data, carga))

    # Progressao: ordena cada lista por data, compara primeira vs ultima
    progrediu = iguais = regrediu = 0
    for chaves, lista in progressao.items():
        if len(lista) < 2:
            continue
        lista.sort(key=lambda t: t[0])
        primeira = lista[0][1]
        ultima = lista[-1][1]
        if ultima > primeira:
            progrediu += 1
        elif ultima < primeira:
            regrediu += 1
        else:
            iguais += 1

    alunos_com_exec = set(sessoes_por_aluno.keys())
    n_sessoes = len(sessoes_set)
    n_alunos_treinaram = len(alunos_com_exec)
    series_total = sum(series_por_aluno.values())

    # Top alunos por numero de sessoes
    top = []
    for cid, sessoes in sessoes_por_aluno.items():
        top.append({
            "ClienteId": cid,
            "Nome": nome_por_cliente.get(cid, f"#{cid}"),
            "Sessoes": len(sessoes),
            "SeriesTotais": series_por_aluno.get(cid, 0),
        })
    top.sort(key=lambda x: -x["Sessoes"])
    top_5 = top[:5]

    # Alunos que nao treinaram nada (cohort - alunos_com_exec)
    nao_treinaram_ids = cohort_ids - alunos_com_exec
    sem_treinar = [
        {"ClienteId": cid, "Nome": nome_por_cliente.get(cid, f"#{cid}")}
        for cid in nao_treinaram_ids
    ]
    sem_treinar.sort(key=lambda x: x["Nome"])

    # Pior 3 (entre os que treinaram, os com menos sessoes)
    pior_3 = sorted(top, key=lambda x: x["Sessoes"])[:3] if len(top) >= 3 else top

    return MetricasTreinos(
        cohort_size=len(cohort_ids),
        alunos_com_execucao=n_alunos_treinaram,
        sessoes_finalizadas=n_sessoes,
        media_sessoes_por_aluno=(n_sessoes / n_alunos_treinaram) if n_alunos_treinaram else 0.0,
        series_totais=series_total,
        media_series_por_sessao=(series_total / n_sessoes) if n_sessoes else 0.0,
        exercicios_progrediram=progrediu,
        exercicios_iguais=iguais,
        exercicios_regrediram=regrediu,
        top_alunos=top_5,
        pior_3=pior_3,
        sem_treinar=sem_treinar,
    )
