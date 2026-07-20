"""Remove linhas do RegistroSemanal que batem com (Professor, SemanaInicio).

Util pra corrigir importacoes erradas — ex: aba renomeada pra data errada.

Uso:
    python src/controle_professores/purgar.py \
        --professor "Katiucy Lauser" --semana 2026-05-13 [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from controle_professores.client import open_controle  # noqa: E402
from controle_professores.config import HEADERS_REGISTRO, TAB_REGISTRO  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--professor", required=True)
    parser.add_argument("--semana", required=True, help="SemanaInicio em YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sc = open_controle()
    ws = sc.spreadsheet.worksheet(TAB_REGISTRO)
    valores = ws.get_all_values()
    if not valores:
        print("[purgar] aba vazia, nada a fazer.")
        return 0

    header = valores[0]
    idx_prof = header.index("Professor") if "Professor" in header else None
    idx_sem = header.index("SemanaInicio") if "SemanaInicio" in header else None
    if idx_prof is None or idx_sem is None:
        print("[erro] cabecalho nao tem Professor/SemanaInicio", file=sys.stderr)
        return 1

    a_remover = []
    a_manter = [header]
    for i, row in enumerate(valores[1:], start=2):
        if (len(row) > max(idx_prof, idx_sem)
                and row[idx_prof].strip() == args.professor
                and row[idx_sem].strip() == args.semana):
            a_remover.append((i, row))
        else:
            a_manter.append(row)

    print(f"[purgar] {len(a_remover)} linha(s) a remover (Prof={args.professor}, SemanaInicio={args.semana})")
    for ln, row in a_remover[:10]:
        nome = row[header.index("Nome")] if "Nome" in header else "?"
        print(f"  L{ln}: {nome}")
    if len(a_remover) > 10:
        print(f"  ... +{len(a_remover) - 10}")

    if args.dry_run:
        print("[purgar] dry-run: nada gravado.")
        return 0

    if not a_remover:
        print("[purgar] nada pra remover.")
        return 0

    # Reescreve a aba inteira (mais simples que deletar linhas individuais)
    ws.clear()
    ws.update(values=a_manter, range_name="A1")
    try:
        ws.format("1:1", {"textFormat": {"bold": True}})
    except Exception:
        pass
    print(f"[purgar] [ok] {len(a_remover)} linhas removidas. Total atual: {len(a_manter)-1}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
