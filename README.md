# Portal da Equipe - CT Italo Vieira

Aplicacao web para registro semanal dos professores, retencao, CRM, painel de
segunda e evolucao de treinos.

- Backend: FastAPI e Python.
- Frontend: React e Vite.
- Persistencia: Google Sheets.
- Producao: Docker no Render Free.

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

O `render.yaml` cria um Web Service Docker gratuito. Durante a criacao do
Blueprint, preencha somente no Render as variaveis marcadas como secretas.

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
