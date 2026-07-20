"""Metricas de retencao mensal e semanal por professor.

Conceitos:
- Ativo em M = teve contrato cuja janela [dataInicio, dataEncerramento|dataValidade]
  intersecta o mes M.
- Retencao Status M1 -> M2 = % dos ativos em M1 que continuam ativos em M2
- Retencao Engajamento M1 -> M2 = % dos ativos em M1 que tiveram >= meta
  presencas no mes M2 (revela "fantasmas": contrato vivo mas nao vem)
- Receita preservada = soma do valorTotal dos retidos em M2
- Qualidade do registro = % das (aluno, semana) com Frequencia/Desempenho/Relato
  preenchidos no RegistroSemanal
- Sumico, Queda, Comparativo, Historico = mantidos da versao anterior
"""
from __future__ import annotations

import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from controle_professores.client import (
    get_config_int,
    open_controle,
    open_nextfit_sync,
)
from controle_professores.config import TAB_ALUNOS, TAB_REGISTRO
from controle_professores.presencas import (
    carregar_presencas,
    presencas_por_cliente_no_mes,
    presencas_por_cliente_no_periodo,
    ultimo_acesso_por_cliente,
)
from controle_professores.semana import semana_de


# ----------------------------- Carregamento base -----------------------------

@dataclass
class BaseDados:
    alunos: list[dict[str, Any]]
    registros: list[dict[str, Any]]
    presencas: list[dict[str, Any]]
    contratos: list[dict[str, Any]]
    contratos_base: list[dict[str, Any]]


def carregar_tudo() -> BaseDados:
    sc_cp = open_controle()
    sc_nf = open_nextfit_sync()
    return BaseDados(
        alunos=sc_cp.read_tab_all(TAB_ALUNOS),
        registros=sc_cp.read_tab_all(TAB_REGISTRO),
        presencas=sc_nf.read_tab_all("Presencas"),
        # Contratos usa leitura pt-BR pra preservar valores decimais (ex: "228,14")
        contratos=sc_nf.read_tab_pt_br("ContratosCliente"),
        # ContratosBase guarda a descricao do plano (usada pra agrupar por modalidade)
        contratos_base=sc_nf.read_tab_all("ContratosBase"),
    )


def _to_int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _to_float(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _parse_date(s) -> date | None:
    """Aceita 'YYYY-MM-DDTHH:MM:SS', 'YYYY-MM-DD' ou ''."""
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


# -------------------------- Periodo do mes ------------------------------------

def periodo_mes(ano: int, mes: int) -> tuple[date, date]:
    inicio = date(ano, mes, 1)
    if mes == 12:
        fim = date(ano + 1, 1, 1) - timedelta(days=1)
    else:
        fim = date(ano, mes + 1, 1) - timedelta(days=1)
    return inicio, fim


def proximo_mes(ano: int, mes: int) -> tuple[int, int]:
    if mes == 12:
        return ano + 1, 1
    return ano, mes + 1


def label_mes(ano: int, mes: int) -> str:
    nomes = [
        "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]
    return f"{nomes[mes - 1]} {ano}"


# -------------------------- Atividade por contrato ----------------------------

def _fim_efetivo(contrato: dict, ate: date) -> date:
    """Determina a data de termino efetiva do contrato.
    Prioridade: dataEncerramento > dataSuspensao > dataValidade > 'ate' (aberto).
    """
    enc = _parse_date(contrato.get("dataEncerramento"))
    if enc:
        return enc
    susp = _parse_date(contrato.get("dataSuspensao"))
    if susp:
        return susp
    val = _parse_date(contrato.get("dataValidade"))
    if val:
        # Se a validade ja passou e o contrato nao esta marcado como Ativo,
        # consideramos que terminou na validade. Se Ativo, assume renovado.
        status = str(contrato.get("status") or "").strip()
        if status != "Ativo":
            return val
    # Aberto / em vigor — considera ativo ate a data de referencia
    return ate


def clientes_ativos_no_mes(
    ano: int, mes: int, contratos: list[dict],
) -> set[int]:
    """Retorna set de codigoCliente que tiveram pelo menos um contrato cuja
    janela [dataInicio, fim_efetivo] intersecta o mes informado.
    """
    inicio_mes, fim_mes = periodo_mes(ano, mes)
    out: set[int] = set()
    for ct in contratos:
        cid = _to_int(ct.get("codigoCliente"))
        if cid is None:
            continue
        di = _parse_date(ct.get("dataInicio"))
        if di is None:
            continue
        df = _fim_efetivo(ct, ate=fim_mes)
        # interseccao com [inicio_mes, fim_mes]
        if di <= fim_mes and df >= inicio_mes:
            out.add(cid)
    return out


def _mensalidade_de_contrato(ct: dict) -> float:
    """Calcula a mensalidade efetiva do contrato, normalizando por duracao.

    NextFit guarda `valorTotal` como o valor TOTAL do contrato pelo periodo
    (ex.: 'Mes 3' por R$ 1100 = R$ 366.67/mes). Quando tipoDuracao = 'Mes' e
    tempoDuracao > 1, dividimos pelo numero de meses.

    Tambem aplica um teto sanitario: contratos com valor > R$ 5000/mes
    sao tratados como 0 (provavelmente lancamento errado / anuidade /
    transacao de teste). Esses casos aparecem na tela como "valor suspeito".
    """
    valor_total = _to_float(ct.get("valorTotal")) or _to_float(ct.get("valorOriginal")) or 0.0
    if valor_total <= 0:
        return 0.0

    tipo_dur = str(ct.get("tipoDuracao") or "").strip()
    tempo = _to_int(ct.get("tempoDuracao")) or 1

    if tipo_dur == "Mes" and tempo > 0:
        mensal = valor_total / tempo
    elif tipo_dur == "Ano" and tempo > 0:
        mensal = valor_total / (12 * tempo)
    elif tipo_dur in ("Dia", "Semana") and tempo > 0:
        # contratos diarios/semanais — converte pra mensal aproximada
        dias = tempo if tipo_dur == "Dia" else tempo * 7
        mensal = (valor_total / dias) * 30
    else:
        mensal = valor_total

    # Teto sanitario: contratos com mensalidade > R$ 3000 sao tratados como
    # lancamento errado / anuidade lancada como mensal. Plano top de academia
    # raramente passa de R$ 1500/mes.
    if mensal > 3000:
        return 0.0
    return mensal


def valor_mensal_por_cliente_no_mes(
    ano: int, mes: int, contratos: list[dict],
) -> dict[int, float]:
    """Mensalidade efetiva de cada cliente no mes (maior contrato ativo)."""
    inicio_mes, fim_mes = periodo_mes(ano, mes)
    valores: dict[int, float] = {}
    for ct in contratos:
        cid = _to_int(ct.get("codigoCliente"))
        if cid is None:
            continue
        di = _parse_date(ct.get("dataInicio"))
        if di is None:
            continue
        df = _fim_efetivo(ct, ate=fim_mes)
        if not (di <= fim_mes and df >= inicio_mes):
            continue
        mensal = _mensalidade_de_contrato(ct)
        if mensal <= 0:
            continue
        if cid not in valores or mensal > valores[cid]:
            valores[cid] = mensal
    return valores


# ------------------ Retencao comparativa M1 -> M2 -----------------------------

@dataclass
class LinhaProf:
    professor: str
    ativos_m1: int
    retidos_status: int
    taxa_status: float
    retidos_engajamento: int
    taxa_engajamento: float
    receita_preservada: float
    qualidade_registro: float  # 0..1 (% das semanas-aluno com algo preenchido em M2)
    perdidos: list[dict[str, Any]]
    em_risco: list[dict[str, Any]]
    cohort_ids: set[int]  # IDs dos alunos ativos em M1 (cohort de origem)
    nome_por_cliente: dict[int, str]  # mapa de nomes pra exibir


def _qualidade_registro(
    registros: list[dict],
    cohort_ids: set[int],
    professor: str,
    inicio_mes: date,
    fim_mes: date,
) -> float:
    """Fracao de linhas do RegistroSemanal cuja semana intersecta o mes destino
    e que estao preenchidas (Frequencia/Desempenho/Relato com conteudo).

    Tolerante a diferencas de dia inicial (domingo vs segunda) — usa
    interseccao do periodo [SemanaInicio, SemanaFim] com [inicio_mes, fim_mes].
    """
    if not cohort_ids:
        return 0.0

    semanas_no_mes: set[tuple[int, str]] = set()
    semanas_preenchidas: set[tuple[int, str]] = set()

    for r in registros:
        cid = _to_int(r.get("ClienteId"))
        if cid is None or cid not in cohort_ids:
            continue
        sem_ini_str = str(r.get("SemanaInicio") or "").strip()
        sem_fim_str = str(r.get("SemanaFim") or "").strip()
        if not sem_ini_str:
            continue
        try:
            sem_ini = datetime.strptime(sem_ini_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        try:
            sem_fim = (
                datetime.strptime(sem_fim_str, "%Y-%m-%d").date()
                if sem_fim_str
                else sem_ini + timedelta(days=6)
            )
        except ValueError:
            sem_fim = sem_ini + timedelta(days=6)

        # Intersecta o mes destino?
        if sem_fim < inicio_mes or sem_ini > fim_mes:
            continue

        chave = (cid, sem_ini_str)
        semanas_no_mes.add(chave)
        # Preenchido se algum dos 3 campos tem conteudo (0 conta)
        freq = r.get("Frequencia")
        des = r.get("Desempenho")
        rel = r.get("Relato")
        tem = (
            (freq is not None and str(freq).strip() != "")
            or (des is not None and str(des).strip() != "")
            or (rel is not None and str(rel).strip() != "")
        )
        if tem:
            semanas_preenchidas.add(chave)

    if not semanas_no_mes:
        return 0.0
    return len(semanas_preenchidas) / len(semanas_no_mes)


def retencao_comparativa(
    ano_m1: int, mes_m1: int,
    ano_m2: int, mes_m2: int,
    base: BaseDados | None = None,
    meta_presencas: int | None = None,
) -> dict[str, Any]:
    """Retorna estrutura completa pra renderizar a tela de retencao M1 -> M2."""
    base = base or carregar_tudo()
    if meta_presencas is None:
        meta_presencas = get_config_int("META_PRESENCAS_MES", 8)

    inicio_m1, fim_m1 = periodo_mes(ano_m1, mes_m1)
    inicio_m2, fim_m2 = periodo_mes(ano_m2, mes_m2)

    ativos_m1 = clientes_ativos_no_mes(ano_m1, mes_m1, base.contratos)
    ativos_m2 = clientes_ativos_no_mes(ano_m2, mes_m2, base.contratos)
    pres_m2 = presencas_por_cliente_no_mes(ano_m2, mes_m2, base.presencas)
    valores_m2 = valor_mensal_por_cliente_no_mes(ano_m2, mes_m2, base.contratos)
    valores_m1 = valor_mensal_por_cliente_no_mes(ano_m1, mes_m1, base.contratos)

    # Mapa cliente -> nome (do nosso Alunos atualizado)
    nome_por_cliente: dict[int, str] = {}
    prof_por_cliente: dict[int, str] = {}
    for a in base.alunos:
        cid = _to_int(a.get("ClienteId"))
        if cid is None:
            continue
        nome_por_cliente[cid] = str(a.get("Nome") or "")
        prof_por_cliente[cid] = str(a.get("Professor") or "").strip() or "(sem professor)"

    # Para historicos onde o aluno nao esta mais em Alunos ATIVO
    # ainda assim queremos mostrar o nome / prof "atual" que temos
    def _nome(cid: int) -> str:
        return nome_por_cliente.get(cid, f"#{cid}")

    def _prof(cid: int) -> str:
        return prof_por_cliente.get(cid, "(sem professor)")

    # Por professor: agrega cohort de M1 e calcula retencao
    cohorts: dict[str, list[int]] = defaultdict(list)
    for cid in ativos_m1:
        cohorts[_prof(cid)].append(cid)

    linhas: list[LinhaProf] = []
    total_ativos_m1 = 0
    total_retidos_status = 0
    total_retidos_engaj = 0
    total_receita_preservada = 0.0
    total_receita_inicial = 0.0

    for prof in sorted(cohorts.keys()):
        cohort = cohorts[prof]
        ativos = len(cohort)
        retidos_status_lista: list[int] = []
        retidos_engaj_lista: list[int] = []
        perdidos: list[dict] = []
        em_risco: list[dict] = []
        receita_preservada = 0.0
        receita_inicial_prof = 0.0

        for cid in cohort:
            receita_inicial_prof += valores_m1.get(cid, 0.0)
            esta_ativo_m2 = cid in ativos_m2
            pres = pres_m2.get(cid, 0)
            esta_engajado_m2 = esta_ativo_m2 and pres >= meta_presencas
            if esta_ativo_m2:
                retidos_status_lista.append(cid)
                receita_preservada += valores_m2.get(cid, 0.0)
            else:
                # Perdido — busca info pra exibir
                perdidos.append({
                    "ClienteId": cid,
                    "Nome": _nome(cid),
                    "PresencasM2": pres,
                    "ValorM1": valores_m1.get(cid, 0.0),
                })
            if esta_engajado_m2:
                retidos_engaj_lista.append(cid)
            elif esta_ativo_m2:
                # ativo mas com baixo engajamento -> em risco
                em_risco.append({
                    "ClienteId": cid,
                    "Nome": _nome(cid),
                    "PresencasM2": pres,
                    "MetaM2": meta_presencas,
                })

        taxa_status = (len(retidos_status_lista) / ativos) if ativos else 0.0
        taxa_engaj = (len(retidos_engaj_lista) / ativos) if ativos else 0.0
        qualidade = _qualidade_registro(
            base.registros, set(cohort), prof, inicio_m2, fim_m2,
        )

        linhas.append(LinhaProf(
            professor=prof,
            ativos_m1=ativos,
            retidos_status=len(retidos_status_lista),
            taxa_status=taxa_status,
            retidos_engajamento=len(retidos_engaj_lista),
            taxa_engajamento=taxa_engaj,
            receita_preservada=round(receita_preservada, 2),
            qualidade_registro=qualidade,
            perdidos=sorted(perdidos, key=lambda x: x["Nome"]),
            em_risco=sorted(em_risco, key=lambda x: x["PresencasM2"]),
            cohort_ids=set(cohort),
            nome_por_cliente={cid: nome_por_cliente.get(cid, f"#{cid}") for cid in cohort},
        ))

        total_ativos_m1 += ativos
        total_retidos_status += len(retidos_status_lista)
        total_retidos_engaj += len(retidos_engaj_lista)
        total_receita_preservada += receita_preservada
        total_receita_inicial += receita_inicial_prof

    # Ordena por taxa de status desc, depois por ativos_m1 desc
    linhas.sort(key=lambda l: (-l.taxa_status, -l.ativos_m1))

    return {
        "ano_m1": ano_m1, "mes_m1": mes_m1, "label_m1": label_mes(ano_m1, mes_m1),
        "ano_m2": ano_m2, "mes_m2": mes_m2, "label_m2": label_mes(ano_m2, mes_m2),
        "meta_presencas": meta_presencas,
        "total_ativos_m1": total_ativos_m1,
        "total_retidos_status": total_retidos_status,
        "total_retidos_engaj": total_retidos_engaj,
        "taxa_status_total": (total_retidos_status / total_ativos_m1) if total_ativos_m1 else 0.0,
        "taxa_engaj_total": (total_retidos_engaj / total_ativos_m1) if total_ativos_m1 else 0.0,
        "receita_preservada": round(total_receita_preservada, 2),
        "receita_inicial": round(total_receita_inicial, 2),
        "alunos_perdidos": total_ativos_m1 - total_retidos_status,
        "linhas_prof": linhas,
    }


# ------------------ Retencao por MODALIDADE M1 -> M2 --------------------------

def _norm_txt(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").upper().strip()


def categorizar_modalidade(descricao: str) -> str:
    """Agrupa a descricao do plano (ContratosBase) numa modalidade ampla.
    A ordem importa: o primeiro termo que casar vence (ex.: 'Hyrox livre' -> HYROX).
    """
    d = _norm_txt(descricao)
    if not d:
        return "(sem plano)"
    if "HYROX" in d:
        return "HYROX"
    if "FATBURN" in d:
        return "FATBURN"
    if "KIDS" in d:
        return "KIDS"
    if "QUADRA" in d:
        return "QUADRA"
    if "PERSONAL" in d:
        return "PERSONAL"
    if "ACESSORIA" in d or "ASSESSORIA" in d:
        return "ASSESSORIA"
    if "CONSULTORIA" in d:
        return "CONSULTORIA"
    if "PROJETO" in d:
        return "PROJETO"
    if "FUNCIONARIO" in d:
        return "FUNCIONÁRIOS"
    if "LIVRE" in d:
        return "LIVRE"
    return "Outros"


def _desc_por_contrato_base(contratos_base: list[dict]) -> dict[int, str]:
    out: dict[int, str] = {}
    for cb in contratos_base:
        bid = _to_int(cb.get("id"))
        if bid is not None:
            out[bid] = str(cb.get("descricao") or "").strip()
    return out


def _modalidade_de_cliente_no_mes(
    ano: int, mes: int, contratos: list[dict],
    base_desc: dict[int, str], agrupar: str,
) -> dict[int, str]:
    """Atribui UMA modalidade a cada cliente ativo no mes: a do contrato ativo
    de maior mensalidade (mesma regra do valor_mensal). `agrupar` = 'categoria'
    (agrupa por categoria ampla) ou 'plano' (usa a descricao crua do plano).
    """
    inicio_mes, fim_mes = periodo_mes(ano, mes)
    melhor: dict[int, tuple[float, str]] = {}
    for ct in contratos:
        cid = _to_int(ct.get("codigoCliente"))
        if cid is None:
            continue
        di = _parse_date(ct.get("dataInicio"))
        if di is None:
            continue
        df = _fim_efetivo(ct, ate=fim_mes)
        if not (di <= fim_mes and df >= inicio_mes):
            continue
        cb_id = _to_int(ct.get("codigoContratoBase"))
        desc = base_desc.get(cb_id, "") if cb_id is not None else ""
        mod = categorizar_modalidade(desc) if agrupar == "categoria" else (desc or "(sem plano)")
        mensal = _mensalidade_de_contrato(ct)
        if cid not in melhor or mensal > melhor[cid][0]:
            melhor[cid] = (mensal, mod)
    return {cid: mod for cid, (_m, mod) in melhor.items()}


@dataclass
class LinhaModalidade:
    modalidade: str
    ativos_m1: int
    retidos_status: int
    taxa_status: float
    receita_inicial: float
    receita_preservada: float
    receita_perdida: float
    perdidos: list[dict[str, Any]]


def retencao_por_modalidade(
    ano_m1: int, mes_m1: int,
    ano_m2: int, mes_m2: int,
    base: BaseDados | None = None,
    agrupar: str = "categoria",
) -> dict[str, Any]:
    """Retencao M1 -> M2 agrupada por modalidade (categoria do plano ou plano cru).

    Cada cliente ativo em M1 e contado UMA vez, na modalidade do seu contrato de
    maior valor em M1. Retido = continua ativo (status) em M2.
    """
    base = base or carregar_tudo()
    base_desc = _desc_por_contrato_base(base.contratos_base)

    ativos_m1 = clientes_ativos_no_mes(ano_m1, mes_m1, base.contratos)
    ativos_m2 = clientes_ativos_no_mes(ano_m2, mes_m2, base.contratos)
    valores_m1 = valor_mensal_por_cliente_no_mes(ano_m1, mes_m1, base.contratos)
    valores_m2 = valor_mensal_por_cliente_no_mes(ano_m2, mes_m2, base.contratos)
    mod_por_cliente = _modalidade_de_cliente_no_mes(
        ano_m1, mes_m1, base.contratos, base_desc, agrupar,
    )

    nome_por_cliente: dict[int, str] = {}
    for a in base.alunos:
        cid = _to_int(a.get("ClienteId"))
        if cid is not None:
            nome_por_cliente[cid] = str(a.get("Nome") or "")

    cohorts: dict[str, list[int]] = defaultdict(list)
    for cid in ativos_m1:
        cohorts[mod_por_cliente.get(cid, "(sem plano)")].append(cid)

    linhas: list[LinhaModalidade] = []
    for mod, cohort in cohorts.items():
        ativos = len(cohort)
        retidos = [c for c in cohort if c in ativos_m2]
        receita_inicial = sum(valores_m1.get(c, 0.0) for c in cohort)
        receita_preservada = sum(valores_m2.get(c, 0.0) for c in retidos)
        # Receita perdida = mensalidade (em M1) de quem saiu (nao retido em M2)
        receita_perdida = sum(valores_m1.get(c, 0.0) for c in cohort if c not in ativos_m2)
        perdidos = sorted(
            [
                {
                    "ClienteId": c,
                    "Nome": nome_por_cliente.get(c, f"#{c}"),
                    "ValorM1": valores_m1.get(c, 0.0),
                }
                for c in cohort if c not in ativos_m2
            ],
            key=lambda x: x["Nome"],
        )
        linhas.append(LinhaModalidade(
            modalidade=mod,
            ativos_m1=ativos,
            retidos_status=len(retidos),
            taxa_status=(len(retidos) / ativos) if ativos else 0.0,
            receita_inicial=round(receita_inicial, 2),
            receita_preservada=round(receita_preservada, 2),
            receita_perdida=round(receita_perdida, 2),
            perdidos=perdidos,
        ))

    linhas.sort(key=lambda l: (-l.ativos_m1, l.modalidade))

    total_ativos = sum(l.ativos_m1 for l in linhas)
    total_retidos = sum(l.retidos_status for l in linhas)
    return {
        "label_m1": label_mes(ano_m1, mes_m1),
        "label_m2": label_mes(ano_m2, mes_m2),
        "total_ativos_m1": total_ativos,
        "total_retidos_status": total_retidos,
        "taxa_status_total": (total_retidos / total_ativos) if total_ativos else 0.0,
        "receita_inicial": round(sum(l.receita_inicial for l in linhas), 2),
        "receita_preservada": round(sum(l.receita_preservada for l in linhas), 2),
        "receita_perdida": round(sum(l.receita_perdida for l in linhas), 2),
        "linhas": linhas,
    }


# --------------------- Comparativo digitado x real ----------------------------

def comparativo_semana(
    inicio: date,
    base: BaseDados | None = None,
) -> list[dict[str, Any]]:
    """Compara, por aluno na semana `inicio`, a frequencia digitada pelo prof
    com as presencas reais. Retorna list[dict] com diferencas.
    """
    base = base or carregar_tudo()
    fim = inicio + timedelta(days=6)
    pres_periodo = presencas_por_cliente_no_periodo(inicio, fim, base.presencas)
    chave = inicio.isoformat()

    registros_da_semana = [r for r in base.registros if str(r.get("SemanaInicio") or "").strip() == chave]

    out: list[dict] = []
    for r in registros_da_semana:
        cid = _to_int(r.get("ClienteId"))
        if cid is None:
            continue
        # cuidado: r.get("Frequencia") pode ser 0 (int) — usar "is None" pra distinguir de vazio
        freq_raw = r.get("Frequencia")
        digitada_raw = "" if freq_raw is None else str(freq_raw).strip()
        digitada_num = _to_int(digitada_raw)
        real = pres_periodo.get(cid, 0)
        out.append({
            "ClienteId": cid,
            "Nome": r.get("Nome", ""),
            "Professor": r.get("Professor", ""),
            "FreqDigitada": digitada_raw,
            "FreqDigitadaNum": digitada_num,
            "FreqReal": real,
            "Diferenca": (digitada_num - real) if digitada_num is not None else None,
        })
    out.sort(key=lambda r: ((r["Professor"] or ""), -(abs(r["Diferenca"]) if r["Diferenca"] is not None else -1)))
    return out


# ------------------------ Alertas de sumico -----------------------------------

def alertas_sumico(
    base: BaseDados | None = None,
    dias: int | None = None,
    modo: str = "max",
) -> list[dict[str, Any]]:
    """Lista alunos ATIVOS filtrados por dias_sem_vir.

    - modo='max'  -> mostra alunos com dias_sem_vir <= `dias` (faltas ate X)
                     ordenados do MAIOR para o MENOR (proximos do limite primeiro)
    - modo='min'  -> mostra alunos com dias_sem_vir > `dias` (sumiram ha mais de X)
                     ordenados do MAIOR para o MENOR (mais sumidos primeiro)
    """
    base = base or carregar_tudo()
    if dias is None:
        dias = get_config_int("DIAS_SUMICO_ALERTA", 14)
    hoje = date.today()
    ult = ultimo_acesso_por_cliente(base.presencas)

    out: list[dict] = []
    for a in base.alunos:
        if str(a.get("Status")).strip().upper() != "ATIVO":
            continue
        cid = _to_int(a.get("ClienteId"))
        if cid is None:
            continue
        ultima = ult.get(cid)
        dias_sem = (hoje - ultima).days if ultima else None

        if modo == "max":
            # Inclui apenas quem tem dias_sem_vir <= dias (com presenca registrada)
            if dias_sem is None or dias_sem > dias:
                continue
        else:  # modo == "min"
            # Inclui quem tem dias_sem_vir > dias OU nunca veio
            if dias_sem is not None and dias_sem <= dias:
                continue

        out.append({
            "ClienteId": cid,
            "Nome": a.get("Nome", ""),
            "Professor": a.get("Professor", ""),
            "UltimoAcesso": ultima.isoformat() if ultima else "",
            "DiasSemVir": dias_sem if dias_sem is not None else "(nunca)",
        })

    # Ordena: mais dias sem vir primeiro (em ambos os modos)
    out.sort(
        key=lambda r: (
            r["DiasSemVir"] if isinstance(r["DiasSemVir"], int) else 99999,
            r["Professor"] or "",
        ),
        reverse=True,
    )
    return out


def alunos_recentes(
    base: BaseDados | None = None,
    dias: int = 7,
) -> list[dict[str, Any]]:
    """Inverso do sumico: alunos ATIVOS que vieram nos ULTIMOS `dias` dias.

    Util pra ver quem esta engajado / treinando agora.
    """
    base = base or carregar_tudo()
    hoje = date.today()
    limite = hoje - timedelta(days=dias)
    ult = ultimo_acesso_por_cliente(base.presencas)

    out: list[dict] = []
    for a in base.alunos:
        if str(a.get("Status")).strip().upper() != "ATIVO":
            continue
        cid = _to_int(a.get("ClienteId"))
        if cid is None:
            continue
        ultima = ult.get(cid)
        if ultima is None or ultima < limite:
            continue
        dias_desde = (hoje - ultima).days
        out.append({
            "ClienteId": cid,
            "Nome": a.get("Nome", ""),
            "Professor": a.get("Professor", ""),
            "UltimoAcesso": ultima.isoformat(),
            "DiasDesdeUltimo": dias_desde,
        })
    # Ordena: mais recentes primeiro, depois alfabetico por prof
    out.sort(key=lambda r: (r["DiasDesdeUltimo"], r["Professor"] or "", r["Nome"]))
    return out


# --------------------- Historico individual do aluno --------------------------

def historico_aluno(
    cliente_id: int,
    base: BaseDados | None = None,
) -> dict[str, Any]:
    """Linha do tempo do aluno: registros semanais + presencas reais por semana."""
    base = base or carregar_tudo()
    regs = [r for r in base.registros if _to_int(r.get("ClienteId")) == cliente_id]
    regs.sort(key=lambda r: str(r.get("SemanaInicio") or ""))

    # presencas reais agregadas por semana
    pres_por_semana: dict[date, int] = defaultdict(int)
    for p in base.presencas:
        if _to_int(p.get("CodigoCliente")) != cliente_id:
            continue
        try:
            dt = datetime.fromisoformat(str(p.get("Data") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        sem_ini, _ = semana_de(dt.date())
        pres_por_semana[sem_ini] += 1

    timeline: list[dict] = []
    for r in regs:
        sem_ini_str = str(r.get("SemanaInicio") or "").strip()
        try:
            sem_ini = datetime.strptime(sem_ini_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        freq_raw = r.get("Frequencia")
        timeline.append({
            "SemanaInicio": sem_ini_str,
            "SemanaFim": str(r.get("SemanaFim") or ""),
            "FreqDigitada": "" if freq_raw is None else str(freq_raw),
            "FreqReal": pres_por_semana.get(sem_ini, 0),
            "Desempenho": str(r.get("Desempenho") or ""),
            "Relato": str(r.get("Relato") or ""),
            "AtualizadoEm": str(r.get("AtualizadoEm") or ""),
        })

    aluno = next((a for a in base.alunos if _to_int(a.get("ClienteId")) == cliente_id), None)
    return {
        "Aluno": aluno or {},
        "Timeline": timeline,
    }


# ------------------ Queda de frequencia ---------------------------------------

def queda_frequencia(
    base: BaseDados | None = None,
    semanas_compara: int = 4,
) -> list[dict[str, Any]]:
    """Detecta alunos cuja media de presencas nas ultimas N semanas caiu
    em relacao as N semanas anteriores.
    """
    base = base or carregar_tudo()
    hoje = date.today()
    sem_atual_ini, _ = semana_de(hoje)

    inicio_recente = sem_atual_ini - timedelta(days=7 * (semanas_compara - 1))
    inicio_anterior = sem_atual_ini - timedelta(days=7 * (2 * semanas_compara - 1))
    fim_recente = sem_atual_ini + timedelta(days=6)
    fim_anterior = inicio_recente - timedelta(days=1)

    pres_recente = presencas_por_cliente_no_periodo(inicio_recente, fim_recente, base.presencas)
    pres_anterior = presencas_por_cliente_no_periodo(inicio_anterior, fim_anterior, base.presencas)

    out: list[dict] = []
    for a in base.alunos:
        if str(a.get("Status")).strip().upper() != "ATIVO":
            continue
        cid = _to_int(a.get("ClienteId"))
        if cid is None:
            continue
        media_recente = pres_recente.get(cid, 0) / semanas_compara
        media_anterior = pres_anterior.get(cid, 0) / semanas_compara
        delta = media_recente - media_anterior
        if media_anterior > 0 and delta <= -1.0:
            out.append({
                "ClienteId": cid,
                "Nome": a.get("Nome", ""),
                "Professor": a.get("Professor", ""),
                "MediaAnterior": round(media_anterior, 2),
                "MediaRecente": round(media_recente, 2),
                "Delta": round(delta, 2),
            })
    out.sort(key=lambda r: r["Delta"])
    return out
