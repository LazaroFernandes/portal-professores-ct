"""Operacoes de escrita pontual na aba Alunos (atributos por aluno).

Diferente de sync_alunos (que reescreve a aba inteira a partir do NextFit), aqui
ficam edicoes feitas pelo professor no app que devem persistir entre semanas —
hoje so o Turno.
"""
from __future__ import annotations

import gspread

from controle_professores.client import open_controle
from controle_professores.config import TAB_ALUNOS


def set_turno(cliente_id: int, turno: str, sc=None) -> str:
    """Grava o Turno de um aluno na aba Alunos (acha a linha por ClienteId).

    Retorna 'updated', 'not_found' ou 'no_columns'.
    """
    sc = sc or open_controle()
    ws = sc.spreadsheet.worksheet(TAB_ALUNOS)
    valores = ws.get_all_values()
    if not valores:
        return "not_found"
    header = valores[0]
    idx = {h: i for i, h in enumerate(header)}
    if "ClienteId" not in idx or "Turno" not in idx:
        return "no_columns"

    for r_idx, row in enumerate(valores[1:], start=2):  # 2 = primeira linha de dados
        if len(row) <= idx["ClienteId"]:
            continue
        try:
            cid = int(row[idx["ClienteId"]])
        except (ValueError, IndexError):
            continue
        if cid == int(cliente_id):
            a1 = gspread.utils.rowcol_to_a1(r_idx, idx["Turno"] + 1)
            ws.update(values=[[turno]], range_name=a1)
            return "updated"
    return "not_found"
