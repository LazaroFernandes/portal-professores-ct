"""Funcoes de leitura/escrita do RegistroSemanal (long format).

Centralizam o "como ler e gravar" para que scripts e interfaces web
nao reimplementem a mesma logica varias vezes.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import gspread

from controle_professores.client import open_controle
from controle_professores.config import HEADERS_REGISTRO, TAB_REGISTRO
from controle_professores.semana import fmt_iso, parse_iso


def _agora_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _ws_registro(sc):
    sh = sc.spreadsheet
    try:
        return sh.worksheet(TAB_REGISTRO)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=TAB_REGISTRO, rows=2000, cols=len(HEADERS_REGISTRO))
        ws.update(values=[HEADERS_REGISTRO], range_name="A1")
        ws.format("1:1", {"textFormat": {"bold": True}})
        return ws


def ler_tudo(sc=None) -> list[dict[str, Any]]:
    """Le o RegistroSemanal inteiro como list[dict]."""
    sc = sc or open_controle()
    return sc.read_tab_all(TAB_REGISTRO)


def ler_semana(inicio: date, sc=None) -> list[dict[str, Any]]:
    """Le todas as linhas da semana (segunda especificada como `inicio`)."""
    chave = fmt_iso(inicio)
    return [r for r in ler_tudo(sc) if str(r.get("SemanaInicio") or "").strip() == chave]


def chave_existente(inicio: date, sc=None) -> set[int]:
    """Retorna set de ClienteIds que ja tem linha na semana `inicio`."""
    out: set[int] = set()
    for r in ler_semana(inicio, sc):
        try:
            out.add(int(r["ClienteId"]))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def append_linhas(linhas: list[dict[str, Any]], sc=None) -> int:
    """Adiciona linhas no final da aba (sem reescrever)."""
    if not linhas:
        return 0
    sc = sc or open_controle()
    return sc.append_tab(TAB_REGISTRO, linhas)


def upsert_linha(
    cliente_id: int,
    semana_inicio: date,
    *,
    frequencia: str | None = None,
    desempenho: str | None = None,
    relato: str | None = None,
    sc=None,
) -> str:
    """Atualiza (ou cria) UMA linha do RegistroSemanal pra (cliente, semana).

    Os campos passados como None nao sao tocados (fica o valor existente).
    Retorna 'updated' ou 'inserted'.
    """
    sc = sc or open_controle()
    ws = _ws_registro(sc)
    valores = ws.get_all_values()
    if not valores:
        return "no_header"
    header = valores[0]
    idx = {h: i for i, h in enumerate(header)}

    chave_inicio = fmt_iso(semana_inicio)
    target_row: int | None = None
    target_dados: list[str] | None = None
    for r_idx, row in enumerate(valores[1:], start=2):  # 2 = primeira linha de dados
        if len(row) <= max(idx.get("ClienteId", 0), idx.get("SemanaInicio", 0)):
            continue
        try:
            cid = int(row[idx["ClienteId"]])
        except (ValueError, IndexError):
            continue
        if cid == int(cliente_id) and row[idx["SemanaInicio"]].strip() == chave_inicio:
            target_row = r_idx
            target_dados = row
            break

    if target_row is None:
        # cria nova linha — precisa nome/professor que nao temos aqui;
        # callers devem usar append_linhas() pra criar do zero.
        raise ValueError(
            f"Linha nao encontrada para ClienteId={cliente_id} semana={chave_inicio}. "
            f"Use append_linhas() para criar."
        )

    # Atualiza so as colunas mudadas
    updates: list[tuple[str, str]] = []
    if frequencia is not None:
        col_letter = gspread.utils.rowcol_to_a1(target_row, idx["Frequencia"] + 1)
        updates.append((col_letter, str(frequencia)))
    if desempenho is not None:
        col_letter = gspread.utils.rowcol_to_a1(target_row, idx["Desempenho"] + 1)
        updates.append((col_letter, str(desempenho)))
    if relato is not None:
        col_letter = gspread.utils.rowcol_to_a1(target_row, idx["Relato"] + 1)
        updates.append((col_letter, str(relato)))

    if not updates:
        return "noop"

    # AtualizadoEm sempre atualiza
    col_letter_at = gspread.utils.rowcol_to_a1(target_row, idx["AtualizadoEm"] + 1)
    updates.append((col_letter_at, _agora_iso()))

    # gspread permite batch_update com lista de dicts {range, values}
    body = [{"range": rng, "values": [[val]]} for rng, val in updates]
    ws.batch_update(body)
    return "updated"


def upsert_em_lote(
    items: list[dict[str, Any]],
    sc=None,
) -> tuple[int, int]:
    """Upsert em lote: cada item deve ter ClienteId, Nome, Professor,
    SemanaInicio, SemanaFim, e qualquer subset de Frequencia/Desempenho/Relato.

    Linhas existentes sao atualizadas in-place; linhas novas sao adicionadas
    em append no final.

    Retorna (qtd_atualizadas, qtd_inseridas).
    """
    sc = sc or open_controle()
    ws = _ws_registro(sc)
    valores = ws.get_all_values()
    if not valores:
        # Aba vazia ou sem cabecalho — escreve cabecalho
        ws.update(values=[HEADERS_REGISTRO], range_name="A1")
        valores = [HEADERS_REGISTRO]
    header = valores[0]
    idx = {h: i for i, h in enumerate(header)}

    # Indexa linhas existentes por (ClienteId, SemanaInicio)
    existentes: dict[tuple[int, str], int] = {}
    for r_idx, row in enumerate(valores[1:], start=2):
        if not row or len(row) <= idx.get("SemanaInicio", 0):
            continue
        try:
            cid = int(row[idx["ClienteId"]])
        except (ValueError, IndexError):
            continue
        sem = row[idx["SemanaInicio"]].strip()
        existentes[(cid, sem)] = r_idx

    body: list[dict] = []
    novas: list[dict] = []
    atualizadas = 0

    for it in items:
        try:
            cid = int(it["ClienteId"])
        except (KeyError, ValueError, TypeError):
            continue
        sem = str(it.get("SemanaInicio") or "").strip()
        key = (cid, sem)
        if key in existentes:
            r_idx = existentes[key]
            for campo in ("Nome", "Professor", "SemanaFim", "Frequencia", "Desempenho", "Relato"):
                if campo in it:
                    col_letter = gspread.utils.rowcol_to_a1(r_idx, idx[campo] + 1)
                    body.append({
                        "range": col_letter,
                        "values": [[str(it[campo]) if it[campo] is not None else ""]],
                    })
            col_at = gspread.utils.rowcol_to_a1(r_idx, idx["AtualizadoEm"] + 1)
            body.append({"range": col_at, "values": [[_agora_iso()]]})
            atualizadas += 1
        else:
            row_full = {h: "" for h in HEADERS_REGISTRO}
            for h in HEADERS_REGISTRO:
                if h in it and it[h] is not None:
                    row_full[h] = it[h]
            row_full["AtualizadoEm"] = _agora_iso()
            novas.append(row_full)

    if body:
        ws.batch_update(body)
    inseridas = sc.append_tab(TAB_REGISTRO, novas) if novas else 0
    return atualizadas, inseridas
