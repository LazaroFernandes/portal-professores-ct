# Portal da Equipe - CT Italo Vieira

Aplicacao web para registro semanal dos professores, retencao, CRM, painel de
segunda e evolucao de treinos.

- Backend: FastAPI e Python.
- Frontend: React e Vite.
- Persistencia principal: PostgreSQL na VPS/Coolify.
- Google Sheets: legado/importacao temporaria durante a migracao.
- Producao atual: Docker no Coolify/Hostinger VPS.
- Render: legado; `render.yaml` foi mantido apenas como referencia.

## Estado atual da producao

A producao atual roda no Coolify em `professores.ctitalovieira.com.br`.
As telas principais ja usam PostgreSQL quando `DATABASE_URL` esta configurada:

- `/registro`: consulta a carteira na API NextFit; os registros preenchidos ficam em `portal_registro_semanal`.
- `/vencimentos`: le as tabelas `nf_*` alimentadas pela VPS.
- `/admin/professores`: análise administrativa da carteira ativa por semana, com
  totais e percentuais de preenchimento, registros completos/parciais/em branco,
  filtros por professor, situação e pesquisa, e consulta às semanas registradas.
  O endpoint `GET /api/admin/professors/analysis?start=AAAA-MM-DD` exige perfil
  administrativo e consulta a carteira NextFit e os registros PostgreSQL somente leitura.
  Semanas anteriores usam a carteira ativa **atual**; o professor armazenado no
  registro é exibido quando difere do responsável atual. Frequência zero conta
  como preenchida; um registro completo exige frequência, desempenho e relato.
  Preenchimento não comprova contato realizado. A consulta não sincroniza alunos.

Scheduled Tasks ativas no Coolify:

```text
nextfit-sync        -> API publica NextFit para nf_*
nextfit-v2-sync     -> API V2 NextFit para nf_v2_*
portal-alunos-sync  -> nf_* para portal_alunos
birthday-report     -> relatorio diario de aniversariantes elegiveis
```

Ainda existem partes legadas que podem consultar Google Sheets, especialmente
rotinas antigas/admin nao priorizadas e importacoes temporarias. Nao remova as
credenciais Google ate a migracao dessas partes ser concluida.

## Desenvolvimento local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

Em outro terminal:

```powershell
cd frontend
pnpm install
pnpm dev
```

Abra `http://localhost:5173`.

## Producao local

```powershell
cd frontend
pnpm build
cd ..
$env:APP_ENV="production"
$env:COOKIE_SECURE="false"
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

## Docker

```bash
docker compose up --build
```

Health check: `GET /api/health`.

## Worker NextFit -> PostgreSQL

O comando abaixo executa uma sincronizacao unica da API publica do NextFit para
o PostgreSQL configurado em `DATABASE_URL`:

```bash
python -m nextfit_sync
```

No Coolify, rode como **Scheduled Task** do recurso/app que usa este Dockerfile
ou como execucao manual:

```bash
python -m nextfit_sync
```

Variaveis necessarias: `DATABASE_URL`, `NEXTFIT_API_KEY`, `NEXTFIT_BASE_URL` e
`NEXTFIT_API_VERSION`. Na primeira execucao o worker cria as tabelas `nf_*`,
`sync_runs` e `sync_errors`.

Sugestao de agenda inicial:

```text
0 6,12,18,22 * * *
```

## Worker portal_alunos -> PostgreSQL

Atualiza a tabela `portal_alunos` a partir das tabelas `nf_clientes`,
`nf_usuarios`, `nf_contratos_cliente` e `nf_contratos_base`, preservando ajustes
manuais ja existentes no portal, como `Turno` e `Professor`:

```bash
python -m sync_portal_alunos
```

No Coolify, rode como Scheduled Task alguns minutos depois do `nextfit-sync`:

```text
10 6,12,18,22 * * *
```

## Relatorio diario de aniversariantes

Lista os aniversariantes elegiveis do dia usando `nf_clientes` e
`nf_contratos_cliente` ja sincronizados no PostgreSQL. Elegivel = cliente ativo
ou contrato vencido ha no maximo 3 dias.

```bash
python -m aniversariantes_do_dia
```

Para testar uma data especifica:

```bash
python -m aniversariantes_do_dia --date 2026-08-01
```

No Coolify, rode como Scheduled Task diaria depois do `nextfit-sync` da manha:

```text
30 6 * * *
```

## Importar Google Sheets -> PostgreSQL

Importa todas as abas da planilha principal `GOOGLE_SHEET_ID` e da planilha
`CONTROLE_PROFESSORES_SHEET_ID` para tabelas `sheet_nextfit_*` e
`sheet_controle_*`:

```bash
python -m sheets_to_postgres
```

Este comando preserva cada linha como `payload JSONB`, sem apagar as planilhas.

## Worker NextFit V2 -> PostgreSQL

Sincroniza dados da API interna V2 quando `NEXTFIT_V2_TOKEN`,
`NEXTFIT_V2_REFRESH_TOKEN` e `NEXTFIT_CODIGO_UNIDADE` estiverem configurados:

```bash
python -m nextfit_v2_sync --endpoint presencas
python -m nextfit_v2_sync --endpoint treinos
```

Se o token V2 estiver expirado, o comando registra erro em `sync_errors` e para
sem afetar o sync da API publica.

## Render

O `render.yaml` e legado. A producao atual nao roda no Render; roda no
Coolify/Hostinger VPS.

Se o Render for usado novamente em algum teste, sera obrigatorio configurar
`DATABASE_URL` e as demais variaveis secretas no painel do Render. Sem
`DATABASE_URL`, o app ativa o fallback legado para Google Sheets em partes que
ainda mantem compatibilidade de transicao.

Depois do primeiro deploy, adicione `professores.ctitalovieira.com.br` em
**Settings > Custom Domains** e configure o CNAME indicado no DNS da Hostinger.

Nunca envie `.env`, credenciais Google ou tokens para o GitHub.

## Testes

```powershell
python -m unittest discover -s backend\tests -v
cd frontend
pnpm install --frozen-lockfile
pnpm build
```

O diagnostico completo da migracao esta em
[`docs/migracao-streamlit-auditoria.md`](docs/migracao-streamlit-auditoria.md).

## Operação diária

`/academia` mostra acessos do dia, carteira do professor, ficha/sessão e confirmação
manual de atendimento. `/pendencias` reúne atendimentos anteriores não finalizados.
Administradores veem todos; professores veem apenas a carteira vinculada às visitas.
Há um atendimento por aluno por dia; novas passagens no mesmo dia não reabrem um registro finalizado.
A tela atualiza acessos a cada 15 segundos e treinos a cada 30 segundos enquanto aberta.
Acesso registrado e conclusão de treino **não comprovam presença física nem saída**.

Com `DATABASE_URL`, a persistência usa as três tabelas aditivas `portal_gym_visits`,
`portal_gym_presence_state` e `portal_daily_attendance_records`. A migração idempotente
está em `backend/migrations/001_daily_operation.sql`; não altera registros semanais.
SQLite existe apenas como fallback de desenvolvimento; produção exige PostgreSQL.
O SQLite do protótipo não é importado automaticamente.

A consulta de acessos/treinos usa a API V2 configurada no servidor. Tokens precisam
estar válidos; falhas aparecem na tela com a última atualização bem-sucedida.
O cliente mantém tokens renovados em memória; a configuração do ambiente precisa
continuar válida após reinicializações. Nenhuma nova tarefa agendada é instalada.
A confirmação do atendimento exige a sessão e o CSRF existentes, grava no portal
sem alterar o NextFit e pode ser reaberta para edição.

Publicação: preservar backup do PostgreSQL e imagem anterior; publicar a imagem do
commit revisado; validar `/api/health`, acesso anônimo 401, perfis administrativo e
professor, sincronização, formulário e releitura. Rollback usa a imagem anterior e
preserva as novas tabelas e registros (não desfazer migração com DROP).

### Fonte direta NextFit e equipe ativa (22/10/2026)

A carteira de alunos e o responsável vêm de `Pessoa/GetClientes`,
`Pessoa/GetUsuarios` e `ContratoCliente` da API pública, com cache de 120 segundos.
O vínculo é pelo ID do professor, não pelo autor da ficha nem pelo nome da planilha.
A equipe autorizada tem sete IDs verificados em `services/nextfit_roster.py`.
Professores fora da equipe não autenticam nem mantêm acesso com sessão anterior.
O alias legado de Lucas Fiorio é normalizado sem alterar a senha existente.

Operação diária, carteira semanal e análise administrativa usam essa fonte para
cadastros e vínculo. Registros preenchidos continuam no armazenamento do portal;
turnos manuais legados são preservados como metadado local, sem substituir vínculos
NextFit. A prévia sem PostgreSQL mantém apenas os registros semanais legados no Sheets.
Não há fallback silencioso de responsável: falha na API impede acesso à carteira.
Mudanças de responsável passam a valer após expirar o cache de até 120 segundos.
Alunos sem um dos sete professores ficam sem vínculo; nenhum cadastro é alterado
no NextFit. Esta mudança é de leitura da API.
