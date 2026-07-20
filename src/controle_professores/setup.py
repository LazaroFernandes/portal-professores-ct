"""Inicializa a planilha 'Controle Professores' com as 3 abas e cabecalhos.

Service accounts do Google nao tem cota de Drive propria no plano gratuito,
entao precisamos:
  1. VOCE cria a planilha em branco manualmente em https://sheets.google.com
  2. Clica em 'Compartilhar' e adiciona o email da service account como Editor:
       nextfit-sync@nextfit-sync.iam.gserviceaccount.com
  3. Copia o ID da URL: docs.google.com/spreadsheets/d/<ESTE_ID>/edit
  4. Passa pra esse script:
       python src/controle_professores/setup.py --id <ID_DA_PLANILHA>

Apos rodar, o script salva o ID em CONTROLE_PROFESSORES_SHEET_ID no .env
automaticamente.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from controle_professores.config import (  # noqa: E402
    CONFIG_DEFAULTS,
    HEADERS_ALUNOS,
    HEADERS_CONFIG,
    HEADERS_REGISTRO,
    TAB_ALUNOS,
    TAB_CONFIG,
    TAB_REGISTRO,
)
from sheets_client import SheetsClient  # noqa: E402


def _atualiza_env(sheet_id: str) -> bool:
    """Adiciona/atualiza CONTROLE_PROFESSORES_SHEET_ID no .env. Retorna True se mudou."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return False
    content = env_path.read_text(encoding="utf-8")
    chave = "CONTROLE_PROFESSORES_SHEET_ID"
    nova_linha = f"{chave}={sheet_id}"
    linhas = content.splitlines()
    achou = False
    for i, l in enumerate(linhas):
        if l.startswith(f"{chave}="):
            linhas[i] = nova_linha
            achou = True
            break
    if not achou:
        linhas.append("")
        linhas.append("# Controle Professores — planilha dedicada (input dos profs)")
        linhas.append(nova_linha)
    env_path.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return True


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--id",
        required=True,
        help="ID da planilha em branco que voce criou e compartilhou como Editor "
             "com nextfit-sync@nextfit-sync.iam.gserviceaccount.com",
    )
    args = parser.parse_args()

    creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials/service-account.json")
    creds_path = Path(creds_file)
    if not creds_path.is_absolute():
        creds_path = PROJECT_ROOT / creds_path
    if not creds_path.exists():
        print(f"[erro] credenciais nao encontradas: {creds_path}", file=sys.stderr)
        return 1

    sheet_id = args.id.strip()
    print(f"[setup] abrindo planilha {sheet_id}...")
    try:
        sc = SheetsClient(credentials_file=str(creds_path), sheet_id=sheet_id)
        sh = sc.spreadsheet
    except Exception as e:
        print(f"[erro] nao consegui abrir a planilha: {e}", file=sys.stderr)
        print(
            "  Verifique que voce compartilhou como Editor com:\n"
            "  nextfit-sync@nextfit-sync.iam.gserviceaccount.com",
            file=sys.stderr,
        )
        return 1
    print(f"[setup] planilha: '{sh.title}'")

    abas_existentes = {ws.title for ws in sh.worksheets()}

    def _criar_ou_atualizar(titulo: str, headers: list[str], rows_default: int) -> None:
        if titulo in abas_existentes:
            ws = sh.worksheet(titulo)
            existing = ws.row_values(1)
            if existing == headers:
                print(f"  [ok] aba '{titulo}' ja existe com cabecalho correto")
                return
            print(f"  [upd] atualizando cabecalho de '{titulo}'")
            ws.update(values=[headers], range_name="A1")
            ws.format("1:1", {"textFormat": {"bold": True}})
            return
        print(f"  [add] criando aba '{titulo}'")
        ws = sh.add_worksheet(title=titulo, rows=rows_default, cols=len(headers))
        ws.update(values=[headers], range_name="A1")
        ws.format("1:1", {"textFormat": {"bold": True}})

    _criar_ou_atualizar(TAB_ALUNOS, HEADERS_ALUNOS, 200)
    _criar_ou_atualizar(TAB_REGISTRO, HEADERS_REGISTRO, 2000)

    # Config: cria com defaults se nao existir
    if TAB_CONFIG in abas_existentes:
        print(f"  [ok] aba '{TAB_CONFIG}' ja existe (mantendo valores)")
    else:
        print(f"  [add] criando aba '{TAB_CONFIG}' com defaults")
        ws_cfg = sh.add_worksheet(title=TAB_CONFIG, rows=20, cols=len(HEADERS_CONFIG))
        config_rows = [HEADERS_CONFIG] + [[k, v] for k, v in CONFIG_DEFAULTS.items()]
        ws_cfg.update(values=config_rows, range_name="A1")
        ws_cfg.format("1:1", {"textFormat": {"bold": True}})

    # Remove abas default de planilha em branco
    for nome_default in ("Sheet1", "Página1", "Pagina1"):
        if nome_default in abas_existentes and nome_default not in {TAB_ALUNOS, TAB_REGISTRO, TAB_CONFIG}:
            try:
                sh.del_worksheet(sh.worksheet(nome_default))
                print(f"  [rm] aba default '{nome_default}' removida")
            except Exception:
                pass

    if _atualiza_env(sheet_id):
        print(f"[setup] .env atualizado com CONTROLE_PROFESSORES_SHEET_ID={sheet_id}")

    print()
    print("=" * 70)
    print(f"PRONTO. Planilha: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
    print("Proximos passos:")
    print("  1) python src/controle_professores/sync_alunos.py")
    print("  2) python src/controle_professores/abrir_semana.py")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
