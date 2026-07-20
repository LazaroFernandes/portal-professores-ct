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
