"""Importa abas semanais antigas (estilo Lucas) pro RegistroSemanal long-format.

Le todas as abas cujo nome bate com 'DD/MM a DD/MM' e move o conteudo
(NOME, FREQUENCIA, DESEMPENHO, RELATOS) pra RegistroSemanal usando o
ClienteId da aba Alunos como chave.

Como a aba antiga nao tem ano, voce passa --ano (default: ano atual).
A aba 'BASE' e 'SDI' sao ignoradas.

Uso:
    python -m controle_professores.importar_historico \
        --src 1pp1LT9vBiSWt3KDdRWe-Od2ogyxST2sDErrbiyDGlE8 \
        --professor LUCAS \
        --ano 2026

Idempotente: se a linha (ClienteId, SemanaInicio) ja existe, atualiza ao inves
de duplicar.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from datetime import datetime  # noqa: E402

import gspread  # noqa: E402

from controle_professores.client import get_creds_path, open_controle  # noqa: E402
from controle_professores.config import TAB_ALUNOS  # noqa: E402
from controle_professores.matching import construir_indice, match  # noqa: E402
from controle_professores.registro import upsert_em_lote  # noqa: E402
from controle_professores.semana import fmt_iso, parse_label_lucas  # noqa: E402
from sheets_client import SheetsClient  # noqa: E402


WEEK_LABEL_RE = re.compile(r"^\d{1,2}/\d{1,2}\s+a\s+\d{1,2}/\d{1,2}$")
ABAS_IGNORAR = {"BASE", "SDI"}


def listar_abas_semanais(sh) -> list[tuple[str, gspread.Worksheet]]:
    out = []
    for ws in sh.worksheets():
        nome = ws.title.strip()
        if nome.upper() in ABAS_IGNORAR:
            continue
        if WEEK_LABEL_RE.match(nome):
            out.append((nome, ws))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True, help="ID da planilha origem (Lucas, etc.)")
    parser.add_argument("--professor", required=True, help="Nome do professor (ex: LUCAS)")
    parser.add_argument("--ano", type=int, default=datetime.now().year, help="Ano de referencia das abas")
    parser.add_argument("--dry-run", action="store_true", help="So mostra o que seria importado, sem gravar")
    parser.add_argument(
        "--alias",
        action="append",
        default=[],
        help="Mapeamento 'Nome Antigo=Nome Novo' (pode repetir). "
             "Util quando a planilha antiga usa nome diferente do NextFit.",
    )
    parser.add_argument(
        "--rename-tab",
        action="append",
        default=[],
        help="Renomeia label de aba antes de parsear: 'aba origem=aba destino' "
             "(ex.: '13/05 a 17/05=12/04 a 18/04'). Pode repetir.",
    )
    parser.add_argument(
        "--only-tab",
        default="",
        help="Importa SOMENTE essa aba (nome literal). Util pra reprocessar uma so.",
    )
    args = parser.parse_args()

    aliases: dict[str, str] = {}
    for pair in args.alias:
        if "=" not in pair:
            print(f"[aviso] alias invalido (use 'antigo=novo'): {pair}")
            continue
        antigo, novo = pair.split("=", 1)
        aliases[antigo.strip().lower()] = novo.strip()
    if aliases:
        print(f"[import] aliases ativos: {aliases}")

    renames: dict[str, str] = {}
    for pair in args.rename_tab:
        if "=" not in pair:
            print(f"[aviso] rename invalido (use 'origem=destino'): {pair}")
            continue
        origem, destino = pair.split("=", 1)
        renames[origem.strip()] = destino.strip()
    if renames:
        print(f"[import] renames de aba ativos: {renames}")

    # Abre planilha origem (so leitura)
    sc_src = SheetsClient(credentials_file=str(get_creds_path()), sheet_id=args.src)
    sh_src = sc_src.spreadsheet
    print(f"[import] origem: {sh_src.title}")

    # Abre planilha destino + carrega indice de alunos
    sc_dst = open_controle()
    alunos = sc_dst.read_tab_all(TAB_ALUNOS)
    if not alunos:
        print("[erro] aba Alunos vazia. Rode 'python -m controle_professores.sync_alunos' antes.", file=sys.stderr)
        return 1
    indice = construir_indice(alunos)

    abas = listar_abas_semanais(sh_src)
    if not abas:
        print("[import] nenhuma aba semanal encontrada (formato 'DD/MM a DD/MM').")
        return 0
    print(f"[import] {len(abas)} abas semanais identificadas.")

    items_importar: list[dict] = []
    nao_encontrados: list[tuple[str, str]] = []  # (semana, nome)

    for nome_aba, ws in abas:
        if args.only_tab and nome_aba != args.only_tab:
            continue
        # Aplica rename de aba (mesmo conteudo, label de data diferente)
        label_efetivo = renames.get(nome_aba, nome_aba)
        if label_efetivo != nome_aba:
            print(f"  [renomear] aba '{nome_aba}' tratada como '{label_efetivo}'")
        rng = parse_label_lucas(label_efetivo, args.ano)
        if rng is None:
            print(f"  [skip] '{nome_aba}' (label '{label_efetivo}') — nao parseou")
            continue
        ini, fim = rng
        rows = ws.get_all_records()
        n_aba = 0
        for r in rows:
            nome = str(r.get("NOME") or "").strip()
            if not nome:
                continue
            # Aplica alias se houver (case-insensitive)
            if nome.lower() in aliases:
                nome = aliases[nome.lower()]
            # Preserva 0 (int) como digitado — distingue de None/vazio
            freq_raw = r.get("FREQUENCIA")
            freq = "" if freq_raw is None else str(freq_raw).strip()
            desempenho = str(r.get("DESEMPENHO NO TREINO") or r.get("DESEMPENHO") or "").strip()
            relato = str(r.get("RELATOS") or "").strip()
            # Se tudo vazio (incluindo 0 escrito), nao importa (linha de estrutura)
            if freq == "" and not desempenho and not relato:
                continue
            aluno = match(nome, indice)
            if aluno is None:
                nao_encontrados.append((nome_aba, nome))
                continue
            try:
                cid = int(aluno["ClienteId"])
            except (KeyError, ValueError, TypeError):
                continue
            items_importar.append({
                "ClienteId": cid,
                "Nome": aluno.get("Nome", nome),
                "Professor": args.professor,
                "SemanaInicio": fmt_iso(ini),
                "SemanaFim": fmt_iso(fim),
                "Frequencia": freq,
                "Desempenho": desempenho,
                "Relato": relato,
            })
            n_aba += 1
        print(f"  {nome_aba} ({fmt_iso(ini)} a {fmt_iso(fim)}): {n_aba} linhas")

    print(f"[import] total a importar: {len(items_importar)} linhas.")
    if nao_encontrados:
        print(f"[import] {len(nao_encontrados)} nomes nao encontrados na aba Alunos:")
        for sem, nome in nao_encontrados[:20]:
            print(f"  - [{sem}] {nome}")
        if len(nao_encontrados) > 20:
            print(f"  ... +{len(nao_encontrados) - 20}")

    if args.dry_run:
        print("[import] dry-run: nada gravado.")
        return 0

    if not items_importar:
        print("[import] nada pra gravar.")
        return 0

    print("[import] gravando no RegistroSemanal (upsert)...")
    atualizadas, inseridas = upsert_em_lote(items_importar, sc_dst)
    print(f"  [ok] {inseridas} inseridas, {atualizadas} atualizadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
