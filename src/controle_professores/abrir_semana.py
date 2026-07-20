"""Cria as linhas vazias do RegistroSemanal para a semana atual (idempotente).

- Pega lista de alunos ATIVOS da aba Alunos
- Pra cada aluno que ainda NAO tem linha na semana (ClienteId + SemanaInicio),
  insere uma linha em branco pronta pro professor preencher.
- Se a semana ja foi totalmente aberta, nao faz nada.

Pode ser chamado:
- Toda segunda-feira automaticamente (Task Scheduler / cron)
- Pelo botao "Abrir semana atual" na interface do professor
- Manualmente pra abrir uma semana especifica via --inicio YYYY-MM-DD

Uso:
    python -m controle_professores.abrir_semana
    python -m controle_professores.abrir_semana --inicio 2026-05-04
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from controle_professores.client import open_controle  # noqa: E402
from controle_professores.config import TAB_ALUNOS  # noqa: E402
from controle_professores.registro import append_linhas, chave_existente  # noqa: E402
from controle_professores.semana import (  # noqa: E402
    fmt_iso,
    label_semana,
    parse_iso,
    semana_atual,
    semana_de,
)


def abrir_semana(inicio: date | None = None, professor_filtro: str | None = None) -> tuple[int, int]:
    """Abre a semana inserindo linhas vazias pros alunos ativos.

    Retorna (qtd_alunos_ativos, qtd_linhas_inseridas).
    Se professor_filtro for passado, abre so pros alunos daquele prof.
    """
    if inicio is None:
        ini, fim = semana_atual()
    else:
        ini, fim = semana_de(inicio)

    sc = open_controle()
    alunos = sc.read_tab_all(TAB_ALUNOS)
    ativos = [a for a in alunos if str(a.get("Status") or "").strip().upper() == "ATIVO"]
    if professor_filtro:
        ativos = [a for a in ativos if str(a.get("Professor") or "").strip() == professor_filtro]

    ja_existe = chave_existente(ini, sc)
    novas: list[dict] = []
    for a in ativos:
        try:
            cid = int(a["ClienteId"])
        except (KeyError, ValueError, TypeError):
            continue
        if cid in ja_existe:
            continue
        novas.append({
            "ClienteId": cid,
            "Nome": a.get("Nome", ""),
            "Professor": a.get("Professor", ""),
            "SemanaInicio": fmt_iso(ini),
            "SemanaFim": fmt_iso(fim),
            "Frequencia": "",
            "Desempenho": "",
            "Relato": "",
            "AtualizadoEm": "",
        })

    if novas:
        append_linhas(novas, sc)
    return len(ativos), len(novas)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inicio",
        default="",
        help="Segunda-feira da semana (YYYY-MM-DD). Default: semana atual.",
    )
    parser.add_argument(
        "--professor",
        default="",
        help="Filtra so pros alunos deste professor (default: todos).",
    )
    args = parser.parse_args()

    inicio: date | None = None
    if args.inicio.strip():
        inicio = parse_iso(args.inicio.strip())
        if inicio is None:
            print(f"[erro] data invalida: {args.inicio}", file=sys.stderr)
            return 1

    ini = inicio or semana_atual()[0]
    fim = ini + (semana_atual()[1] - semana_atual()[0])
    print(f"[abrir_semana] semana {label_semana(ini, fim)} ({fmt_iso(ini)} a {fmt_iso(fim)})")
    if args.professor:
        print(f"  filtrando por professor: {args.professor}")

    ativos, inseridas = abrir_semana(inicio, args.professor or None)
    print(f"  alunos ativos: {ativos}")
    if inseridas:
        print(f"  [ok] {inseridas} linhas novas inseridas")
    else:
        print("  [ok] semana ja estava aberta — nada a fazer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
