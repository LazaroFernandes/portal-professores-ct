"""Constantes do modulo Controle Professores."""
from __future__ import annotations

# Nomes das abas na planilha "Controle Professores"
TAB_ALUNOS = "Alunos"
TAB_REGISTRO = "RegistroSemanal"
TAB_CONFIG = "Config"
TAB_TAREFAS = "PainelTarefas"

# Cabecalhos das abas (ordem importa — usado em writes/reads)
HEADERS_ALUNOS = [
    "ClienteId",
    "Nome",
    "Turno",
    "Professor",
    "Plano",
    "Modalidade",
    "Status",          # ATIVO | INATIVO
    "AtualizadoEm",
]

HEADERS_REGISTRO = [
    "ClienteId",
    "Nome",
    "Professor",
    "SemanaInicio",    # YYYY-MM-DD (segunda-feira)
    "SemanaFim",       # YYYY-MM-DD (domingo)
    "Frequencia",      # digitada pelo prof
    "Desempenho",      # digitado pelo prof
    "Relato",          # digitado pelo prof
    "AtualizadoEm",    # ISO timestamp da ultima edicao
]

HEADERS_CONFIG = ["Chave", "Valor"]

# Valores default da aba Config
CONFIG_DEFAULTS = {
    "META_PRESENCAS_MES": "8",
    "META_PRESENCAS_SEMANA": "3",
    "DIAS_SUMICO_ALERTA": "14",
}

# Variavel de ambiente que guarda o ID da planilha nova
ENV_SHEET_ID = "CONTROLE_PROFESSORES_SHEET_ID"
