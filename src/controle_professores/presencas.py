"""Helpers de leitura de presencas reais (a aba 'Presencas' da planilha do sync NextFit)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from controle_professores.client import open_nextfit_sync
from controle_professores.semana import semana_de


def _parse_data(s: str) -> datetime | None:
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def carregar_presencas() -> list[dict[str, Any]]:
    """Le a aba 'Presencas' (sincronizada da NextFit) + 'PresencasManuais'
    (lancamentos manuais do gestor pra casos onde a catraca falhou) e devolve
    a uniao. A aba PresencasManuais nao e tocada pelo sync, entao seus
    lancamentos sobrevivem entre execucoes.
    """
    sc = open_nextfit_sync()
    automaticas = sc.read_tab_all("Presencas")
    manuais = sc.read_tab_all("PresencasManuais")  # [] se a aba nao existir
    return automaticas + manuais


def presencas_por_cliente_por_semana(
    presencas: list[dict] | None = None,
) -> dict[int, dict[date, int]]:
    """Conta presencas por (ClienteId, segunda-feira da semana)."""
    presencas = presencas if presencas is not None else carregar_presencas()
    out: dict[int, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    for p in presencas:
        try:
            cid = int(p.get("CodigoCliente"))
        except (TypeError, ValueError):
            continue
        dt = _parse_data(str(p.get("Data") or ""))
        if not dt:
            continue
        sem_ini, _ = semana_de(dt.date())
        out[cid][sem_ini] += 1
    return out


def presencas_por_cliente_no_periodo(
    inicio: date,
    fim: date,
    presencas: list[dict] | None = None,
) -> dict[int, int]:
    """Conta presencas por ClienteId no periodo [inicio, fim] (inclusive)."""
    presencas = presencas if presencas is not None else carregar_presencas()
    out: dict[int, int] = defaultdict(int)
    for p in presencas:
        try:
            cid = int(p.get("CodigoCliente"))
        except (TypeError, ValueError):
            continue
        dt = _parse_data(str(p.get("Data") or ""))
        if not dt:
            continue
        d = dt.date()
        if inicio <= d <= fim:
            out[cid] += 1
    return dict(out)


def presencas_por_cliente_no_mes(
    ano: int, mes: int, presencas: list[dict] | None = None,
) -> dict[int, int]:
    """Conta presencas por ClienteId no mes indicado."""
    inicio = date(ano, mes, 1)
    if mes == 12:
        fim = date(ano + 1, 1, 1) - timedelta(days=1)
    else:
        fim = date(ano, mes + 1, 1) - timedelta(days=1)
    return presencas_por_cliente_no_periodo(inicio, fim, presencas)


def ultimo_acesso_por_cliente(
    presencas: list[dict] | None = None,
) -> dict[int, date]:
    """Retorna a data do ultimo acesso por ClienteId."""
    presencas = presencas if presencas is not None else carregar_presencas()
    out: dict[int, date] = {}
    for p in presencas:
        try:
            cid = int(p.get("CodigoCliente"))
        except (TypeError, ValueError):
            continue
        dt = _parse_data(str(p.get("Data") or ""))
        if not dt:
            continue
        d = dt.date()
        if cid not in out or d > out[cid]:
            out[cid] = d
    return out
