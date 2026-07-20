"""Utilitarios de semana (segunda-domingo) e formatacao de datas."""
from __future__ import annotations

from datetime import date, datetime, timedelta


def semana_de(d: date | datetime) -> tuple[date, date]:
    """Retorna (segunda, domingo) da semana que contem `d`.

    Usa convencao ISO: segunda = inicio, domingo = fim.
    """
    if isinstance(d, datetime):
        d = d.date()
    # weekday(): 0=segunda, 6=domingo
    inicio = d - timedelta(days=d.weekday())
    fim = inicio + timedelta(days=6)
    return inicio, fim


def semana_atual() -> tuple[date, date]:
    return semana_de(date.today())


def fmt_iso(d: date) -> str:
    return d.isoformat()


def fmt_pt(d: date) -> str:
    return d.strftime("%d/%m")


def label_semana(inicio: date, fim: date) -> str:
    """'12/05 a 18/05' — mesmo formato das abas antigas do Lucas."""
    return f"{fmt_pt(inicio)} a {fmt_pt(fim)}"


def parse_iso(s: str) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_label_lucas(label: str, ano_referencia: int) -> tuple[date, date] | None:
    """Tenta extrair (inicio, fim) de uma label tipo '15/03 a 21/03'.

    Como a label nao tem ano, recebe `ano_referencia` para preencher.
    Retorna None se nao conseguiu parsear.
    """
    label = label.strip()
    parts = label.split(" a ")
    if len(parts) != 2:
        return None
    try:
        di = datetime.strptime(parts[0].strip(), "%d/%m").replace(year=ano_referencia).date()
        df = datetime.strptime(parts[1].strip(), "%d/%m").replace(year=ano_referencia).date()
    except ValueError:
        return None
    # Trata virada de ano (ex: "29/12 a 04/01")
    if df < di:
        df = df.replace(year=ano_referencia + 1)
    return di, df


def semanas_entre(inicio: date, fim: date) -> list[tuple[date, date]]:
    """Lista todas as semanas (segunda-domingo) entre `inicio` e `fim` (inclusive)."""
    si, _ = semana_de(inicio)
    _, ff = semana_de(fim)
    out = []
    cur = si
    while cur <= ff:
        out.append((cur, cur + timedelta(days=6)))
        cur = cur + timedelta(days=7)
    return out
