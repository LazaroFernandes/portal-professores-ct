from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from controle_professores import postgres_data
from postgres_store import connect, create_run_tables, finish_run, record_error, start_run


FUSO_LOCAL = ZoneInfo("America/Sao_Paulo")
MARGEM_ATRASO_DIAS = 3


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _data_local(value: object) -> date | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(FUSO_LOCAL)
    return parsed.date()


def _cliente_inativo(cliente: dict) -> bool:
    nested = cliente.get("cliente") or {}
    value = cliente.get("inativo", nested.get("inativo"))
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() in {"TRUE", "VERDADEIRO", "1"}


def _mais_recente(atual: dict | None, candidato: dict) -> dict:
    if atual is None:
        return candidato
    data_atual = _parse_datetime(atual.get("dataInicio"))
    data_candidato = _parse_datetime(candidato.get("dataInicio"))
    if data_candidato is not None and (data_atual is None or data_candidato > data_atual):
        return candidato
    return atual


def _indexar_contratos(contratos: list[dict], hoje: date) -> tuple[dict[int, dict], dict[int, dict]]:
    ativos: dict[int, dict] = {}
    recentes: dict[int, dict] = {}
    for contrato in contratos:
        codigo = contrato.get("codigoCliente")
        if codigo is None:
            continue
        try:
            codigo = int(codigo)
        except (TypeError, ValueError):
            continue
        inicio = _data_local(contrato.get("dataInicio"))
        if inicio is not None and inicio > hoje:
            continue
        recentes[codigo] = _mais_recente(recentes.get(codigo), contrato)
        if str(contrato.get("status") or "").strip() == "Ativo":
            ativos[codigo] = _mais_recente(ativos.get(codigo), contrato)
    return ativos, recentes


def _encerrado_antes_do_vencimento(contrato: dict, validade: date) -> bool:
    for campo in ("dataEncerramento", "dataBloqueio", "dataSuspensao"):
        data_evento = _data_local(contrato.get(campo))
        if data_evento is not None and data_evento < validade:
            return True
    return False


def _situacao_elegivel(
    cliente: dict,
    contrato_ativo: dict | None,
    contrato_recente: dict | None,
    hoje: date,
) -> str | None:
    if not _cliente_inativo(cliente) and contrato_ativo is not None:
        return "ATIVO"

    if contrato_recente is None:
        return None
    status = str(contrato_recente.get("status") or "").strip()
    if status in {"Agendado", "Cancelado", "Erro", "Suspenso"}:
        return None

    validade = _data_local(contrato_recente.get("dataValidade"))
    if validade is None or _encerrado_antes_do_vencimento(contrato_recente, validade):
        return None
    dias_atraso = (hoje - validade).days
    if not 0 <= dias_atraso <= MARGEM_ATRASO_DIAS:
        return None
    unidade = "dia" if dias_atraso == 1 else "dias"
    return f"MARGEM DE RENOVACAO: {dias_atraso} {unidade} (vence/venceu em {validade:%d/%m/%Y})"


def _telefone(cliente: dict) -> str:
    ddd = str(cliente.get("dddFone") or "").strip()
    numero = str(cliente.get("fone") or "").strip()
    if ddd and numero:
        return f"({ddd}) {numero}"
    return numero or ddd or "-"


def buscar_aniversariantes(clientes: list[dict], contratos: list[dict], hoje: date) -> list[dict]:
    ativos, recentes = _indexar_contratos(contratos, hoje)
    resultado = []
    for cliente in clientes:
        nascimento = _data_local(cliente.get("dataNascimento"))
        if nascimento is None or (nascimento.month, nascimento.day) != (hoje.month, hoje.day):
            continue
        codigo = cliente.get("id")
        try:
            codigo = int(codigo)
        except (TypeError, ValueError):
            continue
        situacao = _situacao_elegivel(cliente, ativos.get(codigo), recentes.get(codigo), hoje)
        if situacao is None:
            continue
        resultado.append({
            "nome": str(cliente.get("nome") or "").strip(),
            "codigo": codigo,
            "telefone": _telefone(cliente),
            "nascimento": nascimento.isoformat(),
            "situacao": situacao,
        })
    resultado.sort(key=lambda item: item["nome"].casefold())
    return resultado


def _imprimir_relatorio(aniversariantes: list[dict], hoje: date) -> None:
    print(f"# Aniversariantes elegiveis - {hoje:%d/%m/%Y}")
    print()
    if not aniversariantes:
        print("Nenhum aniversariante elegivel encontrado hoje.")
        return
    print("| Nome | Numero do aluno | Telefone | Nascimento | Situacao |")
    print("|---|---:|---|---|---|")
    for item in aniversariantes:
        nascimento = datetime.strptime(item["nascimento"], "%Y-%m-%d").date()
        print(
            f"| {item['nome']} | {item['codigo']} | {item['telefone']} | "
            f"{nascimento:%d/%m/%Y} | {item['situacao']} |"
        )
    print()
    print(f"Total: {len(aniversariantes)}")


def run(hoje: date | None = None) -> dict:
    hoje = hoje or datetime.now(FUSO_LOCAL).date()
    clientes = postgres_data.read_raw_table("nf_clientes")
    contratos = postgres_data.read_raw_table("nf_contratos_cliente")
    aniversariantes = buscar_aniversariantes(clientes, contratos, hoje)
    return {
        "date": hoje.isoformat(),
        "total": len(aniversariantes),
        "aniversariantes": aniversariantes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="", help="Data local YYYY-MM-DD. Default: hoje em America/Sao_Paulo.")
    args = parser.parse_args()

    load_dotenv()
    hoje = None
    if args.date.strip():
        try:
            hoje = datetime.strptime(args.date.strip(), "%Y-%m-%d").date()
        except ValueError:
            print(f"[erro] data invalida: {args.date}", file=sys.stderr)
            return 1

    try:
        with connect() as conn:
            create_run_tables(conn)
            run_id = start_run(conn, "birthday-report")
            try:
                summary = run(hoje)
                finish_run(conn, run_id, "success", summary)
            except Exception as exc:
                record_error(conn, run_id, "birthday-report", exc)
                finish_run(conn, run_id, "failed", {"error": str(exc)})
                raise
    except Exception as exc:
        print(f"[erro] aniversariantes_do_dia falhou: {exc}", file=sys.stderr)
        return 1

    _imprimir_relatorio(summary["aniversariantes"], datetime.strptime(summary["date"], "%Y-%m-%d").date())
    print()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
