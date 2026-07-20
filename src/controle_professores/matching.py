"""Match de nomes (Lucas's planilha) -> ClienteId do NextFit (aba Alunos)."""
from __future__ import annotations

import unicodedata


def normalizar(s: str) -> str:
    """Lower + strip + remove acentos + colapsa espacos."""
    if not s:
        return ""
    s = s.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())


def construir_indice(alunos_rows: list[dict]) -> dict[str, dict]:
    """Indexa alunos por nome normalizado -> linha original."""
    out: dict[str, dict] = {}
    for a in alunos_rows:
        nome = normalizar(str(a.get("Nome") or ""))
        if not nome:
            continue
        out[nome] = a
    return out


def match(nome: str, indice: dict[str, dict]) -> dict | None:
    """Tenta achar o aluno pelo nome. Tenta:
    1. match exato normalizado
    2. substring nos dois sentidos (1 candidato unico)
    Retorna o dict do aluno ou None.
    """
    n = normalizar(nome)
    if not n:
        return None
    if n in indice:
        return indice[n]
    cands = [k for k in indice if n in k or k in n]
    if len(cands) == 1:
        return indice[cands[0]]
    return None
