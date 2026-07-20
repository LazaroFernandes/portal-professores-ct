# -*- coding: utf-8 -*-
"""Painel de Segunda — orquestrador.

Lê a base sincronizada (DB NEXTFIT no Google Sheets) e computa TODOS os
indicadores que o gestor deve analisar toda segunda-feira, num único snapshot:

  1. Visão geral      : ativos (+variação vs 7d), novos, perdidos, churn%, MRR, ticket
  2. Ligar hoje       : ativos sem vir 30d, queda de frequência (sem vir 7d), vencendo 15d
  3. Churn 60d        : clientes perdidos com data/modalidade/professor (win-back)
  4. Modalidades      : ativos e receita (MRR) por modalidade
  5. Professores      : alunos ativos, frequência 30d, perdas 30d
  6. Financeiro       : receitas/despesas do mês (sem transferências internas),
                        a receber em aberto, tendência 6 meses

Saídas:
  - scripts/_painel_segunda.json   (snapshot que o dashboard lê)
  - scripts/_painel_segunda_hist.json (histórico semanal de KPIs p/ variação)
  - Console: resumo em texto (também vai pro log do .bat)

Rodar:  .venv\\Scripts\\python.exe -X utf8 scripts\\painel_segunda.py
"""
from __future__ import annotations

import json
import os
import sys
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
from controle_professores.client import open_controle, open_nextfit_sync  # noqa: E402

SNAPSHOT = ROOT / "scripts" / "_painel_segunda.json"
HIST = ROOT / "scripts" / "_painel_segunda_hist.json"

HOJE = date.today()
MODALIDADES_OCULTAS_SEM_PROFESSOR = {"FUNCIONARIOS"}

# ----------------------------------------------------------------------------
# Categorias de modalidade (descricao bruta -> categoria). Espelha retorno.py.
# Primeira regra que bate vence.
# ----------------------------------------------------------------------------
_CATEGORIAS: list[tuple[str, list[str]]] = [
    ("ASSESSORIA SEMESTRAL", ["plano", "6 meses"]),
    ("ASSESSORIA SEMESTRAL", ["assessoria", "semestral"]),
    ("ASSESSORIA SEMESTRAL", ["acessoria", "semestral"]),
    ("ASSESSORIA FIXO",      ["acessoria", "fixo"]),
    ("ASSESSORIA FIXO",      ["assessoria", "fixo"]),
    ("CONSULTORIA TREINOS",  ["consultoria", "treinos"]),
    ("CONSULTORIA CRIS",     ["consultoria", "cris"]),
    ("CONSULTORIA ITALO",    ["consultoria", "iv"]),
    ("CONSULTORIA LIVRE",    ["consultoria", "livre"]),
    ("CONSULTORIA LIVRE",    ["trimestral", "livre"]),
    ("CONSULTORIA LIVRE",    ["plano semestral", "livre"]),
    ("CONSULTORIA",          ["consultoria"]),
    ("PERSONAL CRIS",        ["personal", "cris"]),
    ("PERSONAL ITALO",       ["personal", "italo"]),
    ("PERSONAL ITALO",       ["personal", "iv"]),
    ("PERSONAL EQUIPE",      ["personal", "equipe"]),
    ("PERSONAL",             ["personal"]),
    ("HYROX",                ["hyrox"]),
    ("HYROX",                ["black"]),   # 1X/2X/3X/FULL BLACK = HYROX
    ("HYROX",                ["hx"]),      # HX CT = HYROX CT
    ("KIDS",                 ["kids"]),
    ("FATBURN",              ["fatburn"]),
    ("PROJETO",              ["projeto"]),
    ("QUADRA",               ["quadra"]),
    ("PARCERIA",             ["parceria"]),
    ("FUNCIONARIOS",         ["funcionarios"]),
]


def _norm(s: str) -> str:
    d = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in d if unicodedata.category(c) != "Mn").lower().strip()


def categorizar(descricao: str) -> str:
    if not descricao:
        return "(sem contrato)"
    d = _norm(descricao)
    for cat, termos in _CATEGORIAS:
        if all(t in d for t in termos):
            return cat
    return "OUTROS"


# ----------------------------------------------------------------------------
# Parsing helpers
# ----------------------------------------------------------------------------
def parse_date(s) -> date | None:
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "")).date()
    except Exception:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%Y %H:%M:%S"):
            try:
                return datetime.strptime(s[:len(fmt) + 4], fmt).date()
            except Exception:
                pass
    return None


def money(s) -> float:
    if s is None or s == "":
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    txt = str(s).replace("R$", "").strip()
    # pt-BR: 1.234,56 -> 1234.56  ;  548,5 -> 548.5
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return 0.0


def fone_fmt(ddd, fone) -> str:
    ddd = "".join(c for c in str(ddd or "") if c.isdigit())
    f = "".join(c for c in str(fone or "") if c.isdigit())
    if not f:
        return ""
    full = f"{ddd}{f}"
    return full


# ----------------------------------------------------------------------------
# Carregamento da base
# ----------------------------------------------------------------------------
def load_all():
    cli = open_nextfit_sync()
    sh = cli.spreadsheet

    def tab(name):
        ws = sh.worksheet(name)
        vals = ws.get_all_values()
        if not vals:
            return []
        hdr = vals[0]
        return [dict(zip(hdr, row)) for row in vals[1:]]

    # Vínculo aluno -> professor vem da planilha "Controle Professores"
    # (no DB NextFit o codigoUsuarioConsultor quase nunca está preenchido).
    prof_map: dict[str, str] = {}
    cp_id = os.environ.get("CONTROLE_PROFESSORES_SHEET_ID")
    if cp_id:
        try:
            cp = open_controle()
            vals = cp.spreadsheet.worksheet("Alunos").get_all_values()
            hdr = vals[0]
            for row in vals[1:]:
                d = dict(zip(hdr, row))
                cid = (d.get("ClienteId") or "").strip()
                prof = (d.get("Professor") or "").strip()
                if cid and prof:
                    prof_map[cid] = prof
        except Exception as e:  # noqa: BLE001
            print(f"[aviso] não consegui ler Controle Professores: {e}")

    return {
        "clientes": tab("Clientes"),
        "contratos": tab("ContratosCliente"),
        "base": tab("ContratosBase"),
        "usuarios": tab("Usuarios"),
        "presencas": tab("Presencas"),
        "movfin": tab("MovimentosFinanceiros"),
        "receber": tab("ContasReceber"),
        "prof_map": prof_map,
    }


# ----------------------------------------------------------------------------
# Lógica de contratos
# ----------------------------------------------------------------------------
def loss_date(c) -> date | None:
    """Data real de perda do contrato = menor(validade, encerramento, bloqueio)."""
    cands = [
        parse_date(c.get("dataValidade")),
        parse_date(c.get("dataEncerramento")),
        parse_date(c.get("dataBloqueio")),
    ]
    cands = [d for d in cands if d]
    return min(cands) if cands else None


def monthly_value(c) -> float:
    """Valor mensal (MRR) do contrato a partir de valorTotal + duração."""
    v = money(c.get("valorTotal"))
    n = c.get("tempoDuracao") or "1"
    try:
        n = int(float(n))
    except Exception:
        n = 1
    n = max(n, 1)
    dur = (c.get("tipoDuracao") or "").strip()
    if dur == "Mes":
        return v / n
    if dur == "Dia":
        return v * 30.0 / n
    return v


def running_on(c, d: date) -> bool:
    """Contrato estava 'rodando' na data d (para reconstruir ativos históricos)."""
    start = parse_date(c.get("dataInicio"))
    if not start or start > d:
        return False
    if c.get("status") == "Ativo":
        return True
    end = loss_date(c)
    return end is None or end > d


# ----------------------------------------------------------------------------
# Cálculo principal
# ----------------------------------------------------------------------------
def build():
    data = load_all()
    clientes = data["clientes"]
    contratos = data["contratos"]
    base = {b.get("id"): b.get("descricao") for b in data["base"]}
    usuarios = {u.get("id"): u.get("nome") for u in data["usuarios"]}
    presencas = data["presencas"]
    movfin = data["movfin"]
    receber = data["receber"]
    prof_map = data["prof_map"]

    # --- mapas de cliente ---
    cli_by_id = {c.get("id"): c for c in clientes}

    def cli_nome(cid):
        c = cli_by_id.get(cid)
        return c.get("nome") if c else f"#{cid}"

    def cli_fone(cid):
        c = cli_by_id.get(cid)
        if not c:
            return ""
        return fone_fmt(c.get("dddFone"), c.get("fone"))

    def cli_prof(cid):
        p = prof_map.get(cid)
        if p:
            return p
        c = cli_by_id.get(cid)
        if c:
            u = usuarios.get(c.get("codigoUsuarioConsultor"))
            if u:
                return u
        return "(sem professor)"

    def cli_cad(cid):
        c = cli_by_id.get(cid)
        return parse_date(c.get("dataCadastro")) if c else None

    # --- contratos por cliente ---
    contratos_por_cli = defaultdict(list)
    for c in contratos:
        contratos_por_cli[c.get("codigoCliente")].append(c)

    # --- ativos (status = Ativo) ---
    ativos_contr = [c for c in contratos if c.get("status") == "Ativo"]
    ativos_cli = set(c.get("codigoCliente") for c in ativos_contr)

    # contrato "principal" do cliente ativo = maior valor mensal
    contrato_principal = {}
    for c in ativos_contr:
        cid = c.get("codigoCliente")
        mv = monthly_value(c)
        if cid not in contrato_principal or mv > contrato_principal[cid][1]:
            contrato_principal[cid] = (c, mv)

    def modalidade_cli(cid):
        cc = contrato_principal.get(cid)
        if not cc:
            return "(sem contrato)"
        return categorizar(base.get(cc[0].get("codigoContratoBase")))

    # --- ativos históricos (janela) p/ variação ---
    def ativos_em(d: date) -> set:
        out = set()
        for cid, lst in contratos_por_cli.items():
            if any(running_on(c, d) for c in lst):
                out.add(cid)
        return out

    ativos_hoje_win = ativos_em(HOJE)
    ativos_7d = ativos_em(HOJE - timedelta(days=7))
    n_ativos = len(ativos_cli)
    variacao_7d = len(ativos_hoje_win) - len(ativos_7d)

    # --- MRR + ticket ---
    mrr = sum(monthly_value(c) for c in ativos_contr)
    ticket = mrr / n_ativos if n_ativos else 0.0

    # --- novos (últimos 7 dias) ---
    primeiro_contrato = {}  # cid -> menor dataInicio
    for c in contratos:
        cid = c.get("codigoCliente")
        di = parse_date(c.get("dataInicio"))
        if di and (cid not in primeiro_contrato or di < primeiro_contrato[cid]):
            primeiro_contrato[cid] = di
    novos_contratos_7d = sum(
        1 for c in contratos
        if (di := parse_date(c.get("dataInicio"))) and (HOJE - di).days <= 7 and di <= HOJE
    )
    clientes_novos_7d = sum(1 for cid, di in primeiro_contrato.items() if (HOJE - di).days <= 7 and di <= HOJE)

    # --- perdidos (churn) ---
    perdidos = []  # cada: dict
    for cid, lst in contratos_por_cli.items():
        if cid in ativos_cli:
            continue  # ainda ativo, não é perda
        # contrato que terminou por último
        with_loss = [(loss_date(c), c) for c in lst]
        with_loss = [(d, c) for d, c in with_loss if d]
        if not with_loss:
            continue
        d_perda, c_last = max(with_loss, key=lambda x: x[0])
        if d_perda > HOJE:
            continue
        dias = (HOJE - d_perda).days
        perdidos.append({
            "cid": cid,
            "nome": cli_nome(cid),
            "telefone": cli_fone(cid),
            "modalidade": categorizar(base.get(c_last.get("codigoContratoBase"))),
            "professor": cli_prof(cid),
            "data_perda": d_perda.isoformat(),
            "dias": dias,
            "valor_mensal": round(monthly_value(c_last), 2),
        })
    perdidos.sort(key=lambda x: x["dias"])
    perdidos_7d = [p for p in perdidos if p["dias"] <= 7]
    perdidos_30d = [p for p in perdidos if p["dias"] <= 30]
    perdidos_60d = [p for p in perdidos if p["dias"] <= 60]

    churn_30d_pct = round(100 * len(perdidos_30d) / max(n_ativos + len(perdidos_30d), 1), 1)
    receita_perdida_60d = round(sum(p["valor_mensal"] for p in perdidos_60d), 2)

    # --- presenças: última por cliente + contagens de janela ---
    ult_presenca = {}
    pres_7d = defaultdict(int)
    pres_30d = defaultdict(int)
    pres_8a30 = defaultdict(int)
    for p in presencas:
        cid = p.get("CodigoCliente")
        d = parse_date(p.get("Data"))
        if not d:
            continue
        if cid not in ult_presenca or d > ult_presenca[cid]:
            ult_presenca[cid] = d
        dias = (HOJE - d).days
        if 0 <= dias <= 7:
            pres_7d[cid] += 1
        if 0 <= dias <= 30:
            pres_30d[cid] += 1
        if 8 <= dias <= 30:
            pres_8a30[cid] += 1

    # --- LIGAR HOJE: ativos sem vir 30d ---
    sem_vir_30d = []
    for cid in ativos_cli:
        up = ult_presenca.get(cid)
        dias = (HOJE - up).days if up else 999
        if dias >= 30:
            sem_vir_30d.append({
                "nome": cli_nome(cid), "telefone": cli_fone(cid),
                "modalidade": modalidade_cli(cid), "professor": cli_prof(cid),
                "ultima_presenca": up.isoformat() if up else "—",
                "dias": dias if up else None,
            })
    sem_vir_30d.sort(key=lambda x: (x["dias"] is None, -(x["dias"] or 0)))

    # --- LIGAR HOJE: queda de frequência (veio 8-30d, sumiu 7d) ---
    sem_vir_7d_queda = []
    for cid in ativos_cli:
        if pres_7d.get(cid, 0) == 0 and pres_8a30.get(cid, 0) >= 1:
            up = ult_presenca.get(cid)
            sem_vir_7d_queda.append({
                "nome": cli_nome(cid), "telefone": cli_fone(cid),
                "modalidade": modalidade_cli(cid), "professor": cli_prof(cid),
                "ultima_presenca": up.isoformat() if up else "—",
                "freq_30d": pres_8a30.get(cid, 0),
            })
    sem_vir_7d_queda.sort(key=lambda x: -x["freq_30d"])

    # --- LIGAR HOJE: vencendo nos próximos 15 dias (renovação) ---
    vencendo_15d = []
    for c in ativos_contr:
        v = parse_date(c.get("dataValidade"))
        if not v:
            continue
        dias = (v - HOJE).days
        if 0 <= dias <= 15:
            cid = c.get("codigoCliente")
            vencendo_15d.append({
                "nome": cli_nome(cid), "telefone": cli_fone(cid),
                "modalidade": categorizar(base.get(c.get("codigoContratoBase"))),
                "professor": cli_prof(cid),
                "validade": v.isoformat(), "dias": dias,
                "recorrente": str(c.get("recorrente")).upper() in ("VERDADEIRO", "TRUE"),
                "valor_mensal": round(monthly_value(c), 2),
            })
    vencendo_15d.sort(key=lambda x: x["dias"])
    vencendo_7d = [v for v in vencendo_15d if v["dias"] <= 7]
    # prioridade de renovação: vence em 7d E não renova sozinho
    vencendo_7d_acao = [v for v in vencendo_7d if not v["recorrente"]]

    # --- MODALIDADES ---
    mod_ativos = defaultdict(int)
    mod_mrr = defaultdict(float)
    for cid in ativos_cli:
        mod_ativos[modalidade_cli(cid)] += 1
    for c in ativos_contr:
        mod = categorizar(base.get(c.get("codigoContratoBase")))
        mod_mrr[mod] += monthly_value(c)
    modalidades = sorted(
        [{"modalidade": m, "ativos": mod_ativos.get(m, 0), "mrr": round(mod_mrr.get(m, 0), 2)}
         for m in set(list(mod_ativos) + list(mod_mrr))],
        key=lambda x: -x["mrr"],
    )

    # --- PROFESSORES ---
    prof_ativos = defaultdict(int)
    prof_pres = defaultdict(int)
    for cid in ativos_cli:
        p = cli_prof(cid)
        prof_ativos[p] += 1
        prof_pres[p] += pres_30d.get(cid, 0)
    prof_perdas = defaultdict(int)
    for p in perdidos_30d:
        prof_perdas[p["professor"]] += 1
    professores = []
    for p, n in prof_ativos.items():
        professores.append({
            "professor": p, "ativos": n,
            "freq_media_30d": round(prof_pres[p] / n, 1) if n else 0,
            "perdidos_30d": prof_perdas.get(p, 0),
        })
    professores.sort(key=lambda x: -x["ativos"])

    # --- SEM PROFESSOR (ativos sem vínculo de professor) ---
    sem_professor = []
    for cid in ativos_cli:
        if cli_prof(cid) == "(sem professor)":
            modalidade = modalidade_cli(cid)
            if modalidade in MODALIDADES_OCULTAS_SEM_PROFESSOR:
                continue
            up = ult_presenca.get(cid)
            cad = cli_cad(cid)
            sem_professor.append({
                "nome": cli_nome(cid), "telefone": cli_fone(cid),
                "modalidade": modalidade,
                "ultima_presenca": up.isoformat() if up else "—",
                "dias_sem_vir": (HOJE - up).days if up else None,
                "data_cadastro": cad.isoformat() if cad else "—",
            })
    sem_professor.sort(key=lambda x: (x["modalidade"], x["nome"]))

    # --- NOVOS & REATIVADOS (1º cadastro ou volta após 30+ dias parado) ---
    JANELA_NOVOS = 30
    novos_reativados = []
    for cid, lst in contratos_por_cli.items():
        started = [(parse_date(c.get("dataInicio")), c) for c in lst if parse_date(c.get("dataInicio"))]
        in_win = [(d, c) for d, c in started if 0 <= (HOJE - d).days <= JANELA_NOVOS]
        if not in_win:
            continue
        d_start, c = max(in_win, key=lambda x: x[0])
        first = primeiro_contrato.get(cid)
        gap = None
        if first and d_start == first:
            tipo = "Novo (1º cadastro)"
        else:
            prev_ends = [loss_date(pc) for pc in lst
                         if parse_date(pc.get("dataInicio")) and parse_date(pc.get("dataInicio")) < d_start]
            prev_ends = [e for e in prev_ends if e]
            if not prev_ends:
                continue
            gap = (d_start - max(prev_ends)).days
            if gap < 30:
                continue  # renovação normal, não é reativação
            tipo = "Reativado"
        novos_reativados.append({
            "nome": cli_nome(cid), "telefone": cli_fone(cid),
            "tipo": tipo,
            "modalidade": categorizar(base.get(c.get("codigoContratoBase"))),
            "professor": cli_prof(cid),
            "data_entrada": d_start.isoformat(),
            "dias": (HOJE - d_start).days,
            "dias_parado": gap if gap is not None else "—",
            "status": c.get("status"),
        })
    novos_reativados.sort(key=lambda x: x["dias"])

    # --- FINANCEIRO (mês corrente, sem transferências internas) ---
    def is_transfer(desc):
        return "transfer" in _norm(desc)

    mes_ini = HOJE.replace(day=1)

    def soma_mes(tipo, d_ref):
        tot = 0.0
        for m in movfin:
            if m.get("tipo") != tipo:
                continue
            if is_transfer(m.get("descricao")):
                continue
            d = parse_date(m.get("dataEfetivacao")) or parse_date(m.get("dataMovimentacao"))
            if d and d.year == d_ref.year and d.month == d_ref.month:
                tot += money(m.get("valor"))
        return round(tot, 2)

    receitas_mes = soma_mes("Entrada", HOJE)
    despesas_mes = soma_mes("Saida", HOJE)

    # tendência 6 meses (receitas reais)
    receitas_6m = []
    ref = mes_ini
    for _ in range(6):
        receitas_6m.append({"mes": ref.strftime("%Y-%m"), "valor": soma_mes("Entrada", ref)})
        # mês anterior
        ref = (ref - timedelta(days=1)).replace(day=1)
    receitas_6m.reverse()

    # a receber em aberto
    receber_aberto = 0.0
    receber_vencido = 0.0
    for r in receber:
        st = _norm(r.get("status"))
        if st in ("recebido", "cancelado"):
            continue
        val = money(r.get("valor"))
        receber_aberto += val
        dv = parse_date(r.get("dataVencimento"))
        if dv and dv < HOJE:
            receber_vencido += val

    snap = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "data_ref": HOJE.isoformat(),
        "visao_geral": {
            "ativos": n_ativos,
            "ativos_win_hoje": len(ativos_hoje_win),
            "ativos_7d_atras": len(ativos_7d),
            "variacao_7d": variacao_7d,
            "novos_contratos_7d": novos_contratos_7d,
            "clientes_novos_7d": clientes_novos_7d,
            "perdidos_7d": len(perdidos_7d),
            "perdidos_30d": len(perdidos_30d),
            "perdidos_60d": len(perdidos_60d),
            "churn_30d_pct": churn_30d_pct,
            "mrr": round(mrr, 2),
            "ticket_medio": round(ticket, 2),
            "receita_perdida_60d": receita_perdida_60d,
        },
        "ligar_hoje": {
            "sem_vir_30d": sem_vir_30d,
            "sem_vir_7d_queda": sem_vir_7d_queda,
            "vencendo_7d": vencendo_7d,
            "vencendo_7d_acao": vencendo_7d_acao,
            "vencendo_15d": vencendo_15d,
        },
        "churn_60d": perdidos_60d,
        "sem_professor": sem_professor,
        "novos_reativados": novos_reativados,
        "modalidades": modalidades,
        "professores": professores,
        "financeiro": {
            "mes": HOJE.strftime("%Y-%m"),
            "receitas": receitas_mes,
            "despesas": despesas_mes,
            "saldo": round(receitas_mes - despesas_mes, 2),
            "receber_aberto": round(receber_aberto, 2),
            "receber_vencido": round(receber_vencido, 2),
            "receitas_6m": receitas_6m,
        },
    }
    return snap


def salvar_historico(snap):
    hist = []
    if HIST.exists():
        try:
            hist = json.loads(HIST.read_text(encoding="utf-8"))
        except Exception:
            hist = []
    vg = snap["visao_geral"]
    hist = [h for h in hist if h.get("data_ref") != snap["data_ref"]]
    hist.append({
        "data_ref": snap["data_ref"],
        "ativos": vg["ativos"], "mrr": vg["mrr"],
        "perdidos_30d": vg["perdidos_30d"], "churn_30d_pct": vg["churn_30d_pct"],
        "novos_contratos_7d": vg["novos_contratos_7d"],
    })
    hist.sort(key=lambda x: x["data_ref"])
    HIST.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")


def print_resumo(snap):
    vg = snap["visao_geral"]
    fin = snap["financeiro"]
    print("=" * 64)
    print(f"PAINEL DE SEGUNDA — {snap['data_ref']}  (gerado {snap['gerado_em']})")
    print("=" * 64)
    sinal = "+" if vg["variacao_7d"] >= 0 else ""
    print(f"Ativos: {vg['ativos']}  ({sinal}{vg['variacao_7d']} vs 7d)   "
          f"MRR: R$ {vg['mrr']:,.2f}   Ticket: R$ {vg['ticket_medio']:,.2f}")
    print(f"Novos 7d: {vg['novos_contratos_7d']} contratos / {vg['clientes_novos_7d']} clientes novos")
    print(f"Perdidos: 7d={vg['perdidos_7d']}  30d={vg['perdidos_30d']}  60d={vg['perdidos_60d']}  "
          f"| Churn 30d: {vg['churn_30d_pct']}%  | Receita perdida 60d: R$ {vg['receita_perdida_60d']:,.2f}")
    print("-" * 64)
    lh = snap["ligar_hoje"]
    print(f"LIGAR HOJE: sem vir 30d={len(lh['sem_vir_30d'])}  "
          f"queda freq (7d)={len(lh['sem_vir_7d_queda'])}  "
          f"vence 7d={len(lh['vencendo_7d'])} (renovar: {len(lh['vencendo_7d_acao'])})")
    print(f"NOVOS & REATIVADOS (30d)={len(snap['novos_reativados'])}  "
          f"ATIVOS SEM PROFESSOR={len(snap['sem_professor'])}")
    print("-" * 64)
    print("MODALIDADES (ativos · MRR):")
    for m in snap["modalidades"][:12]:
        print(f"  {m['modalidade']:<22} {m['ativos']:>4} ativos   R$ {m['mrr']:>10,.2f}")
    print("-" * 64)
    print("PROFESSORES (ativos · freq30d · perdas30d):")
    for p in snap["professores"][:12]:
        print(f"  {p['professor']:<28} {p['ativos']:>4}   {p['freq_media_30d']:>5}   {p['perdidos_30d']:>3}")
    print("-" * 64)
    print(f"FINANCEIRO {fin['mes']}: receitas R$ {fin['receitas']:,.2f}  "
          f"despesas R$ {fin['despesas']:,.2f}  saldo R$ {fin['saldo']:,.2f}")
    print(f"  A receber em aberto: R$ {fin['receber_aberto']:,.2f}  "
          f"(vencido: R$ {fin['receber_vencido']:,.2f})")
    print("=" * 64)


def main():
    snap = build()
    SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    salvar_historico(snap)
    print_resumo(snap)
    print(f"\n[ok] snapshot salvo em {SNAPSHOT}")


if __name__ == "__main__":
    main()
