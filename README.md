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

- `/registro`: le/escreve `portal_alunos` e `portal_registro_semanal`.
- `/vencimentos`: le as tabelas `nf_*` alimentadas pela VPS.

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
