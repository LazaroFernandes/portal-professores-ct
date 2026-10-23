# Prévia local: registro diário, análise e ações

Implementação na branch `codex/fluxo-diario-gerencia`. Não publicada.

## Testar

Iniciar na raiz do projeto: `.venv312/bin/python scripts/preview_daily.py`.
Abrir http://127.0.0.1:8002. Acessos exclusivamente fictícios:

- Professor (Anderson): `ProfessorDemo2026`
- Gerente: `GerenteDemo2026`

Use Sair para alternar os perfis. O banco demonstrativo fica em
`/tmp/portal-workflow-demo-20261022.sqlite` e preserva os testes após reinício.
Para outro cenário limpo, passe um novo caminho em `--database`; não remova bancos reais.
O servidor vincula somente 127.0.0.1, não carrega .env, desliga o agendador,
substitui integrações e bloqueia clientes HTTP externos. Dados sintéticos.
Vencimentos e consulta do histórico semanal real estão indisponíveis nessa prévia.

## Fluxo

1. Professor registra se acompanhou ou não conseguiu observar.
2. Quando acompanhou, informa resultado e desconforto, sem respostas presumidas.
3. Uma única observação é exigida para exceções e pedidos de retorno.
4. Registro alimenta a análise por data/período/professor/situação.
5. Retorno solicitado, desconforto ou treino interrompido abrem ação em revisão.
6. Gerente define orientação, responsável e prazo; professor responsável registra o resultado.
7. Ação resolvida permanece consultável com histórico. Novo relato adverso no mesmo
   registro reabre a revisão, preservando o histórico e exigindo nova conclusão.

O professor deixa de preencher semanal. /registro redireciona ao diário;
as rotas de abertura/gravação semanais retornam 410. Histórico semanal da gerência
permanece somente leitura. A base antiga é preservada por migração aditiva.
A antiga gravação diária também retorna 410 para impedir sobrescrita pelo formulário antigo.

## Regras e limites

- Um registro por acesso de aluno/dia, usando visitas existentes do NextFit.
- Acesso não comprova permanência física na academia.
- Não observado é contabilizado separadamente de registrado/acompanhado.
- Carteira atual controla acesso ao histórico e à gravação diária; autoria e responsável
  no momento do registro são preservados para análise histórica.
- A ação pode ser delegada explicitamente a outro professor pela gerência. Esse professor
  recebe a ação, mas não ganha acesso ao histórico diário completo de outra carteira.
- Ações têm versão otimista, auditoria transacional e proteção CSRF.
- Uma ação por registro; ocorrências em dias diferentes podem criar ações distintas.
- Não há migração retroativa automática de anotações antigas para ações.
- Integração com dados reais e publicação exigem validação posterior à aprovação da prévia.

## Verificação local em 22/10/2026

- 79 testes backend aprovados; 3 testes frontend existentes aprovados.
- 12 testes do contrato diário executados também em PostgreSQL 16 isolado, UTF-8.
- Build Vite aprovado; diff sem erros de whitespace.
- Navegador: professor registrou, gerente recebeu e orientou, professor concluiu,
  gerente visualizou resultado após reinício; consolidação de sete dias conferida.
- Graphify atualizado em modo AST. SQL não foi indexado pelo Graphify por falta
  do parser opcional; as migrações foram verificadas no PostgreSQL real local.

Para repetir PostgreSQL, use uma instância descartável local e banco UTF-8
`portal_workflow_test`, então execute `scripts/check_daily_postgres.py` com
`TEST_DATABASE_URL`. O script limpa somente as tabelas desse banco de teste.
