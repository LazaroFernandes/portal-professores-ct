"""Controle Professores — registro semanal de frequência/desempenho/relato.

Modulos:
- config        — constantes e nomes de aba
- setup         — cria a planilha 'Controle Professores' nova
- sync_alunos   — atualiza aba Alunos a partir do NextFit
- abrir_semana  — cria linhas vazias da semana atual no RegistroSemanal
- importar_historico — importa abas semanais antigas (Lucas etc.) pro long format
- retencao      — calcula metricas de retencao mensal
- semana        — utilitarios de semana (segunda-domingo, formatacao)
"""
