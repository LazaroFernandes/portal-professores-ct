# Auditoria e plano de migração do Streamlit

> Nota de status (2026-07-29): este documento e uma auditoria historica da
> migracao inicial. A producao atual roda em Coolify/Hostinger VPS com
> PostgreSQL como persistencia principal. Google Sheets permanece como legado e
> fonte temporaria de importacao para partes ainda nao migradas.

Data da auditoria: 20/07/2026

## 1. Diagnóstico atual

O repositório não contém uma única aplicação Streamlit. Ele reúne cinco interfaces,
dois clientes da API NextFit, duas planilhas Google usadas como banco, automações de
sincronização e uma aplicação HYROX já construída em FastAPI.

As interfaces Streamlit são:

| Arquivo | Público | Papel atual | Estado |
|---|---|---|---|
| `dashboard/app_professor.py` | Professores e gestor | Login, registro semanal e roteamento para o admin | Produção/nuvem |
| `dashboard/app_admin.py` | Gestor | Retenção, modalidade, presenças, queda, auditoria e histórico | Produção, embutido no app do professor |
| `dashboard/painel_segunda.py` | Gestor | Cockpit semanal, tarefas, listas de ação e financeiro | Produção local |
| `dashboard/retorno.py` | Gestor | CRM de retenção com dez visões e registro de contatos | Auxiliar/legado, ainda funcional |
| `dashboard/app.py` | Gestor | Evolução de treino, carga e volume por grupo muscular | Auxiliar/legado, ainda funcional |

O produto principal usa Python 3.11+, Google Sheets e APIs NextFit. O Google Sheets
é a fonte de persistência existente e será preservado nesta migração. Não há upload de
arquivos nas interfaces atuais. Os downloads existentes são CSV.

### Fontes de dados

- **DB NEXTFIT** (`GOOGLE_SHEET_ID`): clientes, contratos, usuários, presença,
  financeiro, treinos e histórico de execuções.
- **Controle Professores** (`CONTROLE_PROFESSORES_SHEET_ID`): `Alunos`,
  `RegistroSemanal` e `Config`.
- **Snapshots locais**: `_painel_segunda.json`, `_painel_segunda_hist.json` e
  `_painel_tarefas.json`.
- **HYROX**: SQLite próprio em `data/hyrox.db`; já é independente do Streamlit.

### Integrações externas

- API NextFit v1, autenticada por `X-Api-Key`.
- API NextFit v2 interna, autenticada por token e refresh token.
- Google Sheets/Drive via service account (`gspread` e `google-auth`).
- WhatsApp por links `wa.me`; não há envio automático nas telas.

## 2. Funcionalidades encontradas

### Professor

- Login por senha individual e isolamento da carteira do professor.
- Login por senha-mestra para o gestor.
- Navegação por semana, incluindo semanas anteriores e seguintes.
- Abertura idempotente de uma semana ausente.
- Contadores de preenchidos, pendentes e percentual concluído.
- Filtros: pendentes, preenchidos e todos.
- Edição de turno, frequência, desempenho e relato por aluno.
- Salvamento em lote na chave `(ClienteId, SemanaInicio)`.
- Zero em frequência é considerado valor preenchido.

### Administração do controle semanal

- Retenção mês A → mês B, status versus engajamento e meta de presença.
- Indicadores de ativos, retidos, perdidos e receita preservada/perdida.
- Detalhamento por professor e por modalidade/plano.
- Métricas de treino: sessões, alunos engajados, progressão e volume.
- Acompanhamento de alunos recentes/sumidos por janela de dias.
- Queda de frequência entre janelas de semanas.
- Comparação digitado versus presença real por semana.
- Histórico individual do aluno.

### Painel de segunda

- Indicadores de ativos, novos, churn, MRR, ticket e financeiro.
- Checklist semanal de tarefas automáticas e manuais.
- Persistência e reinício das tarefas a cada segunda-feira.
- Listas: sem presença, queda de frequência, renovação, novos/reativados,
  sem professor e churn de 60 dias.
- Carteira e frequência por professor.
- Ativos e MRR por modalidade.
- Tendência financeira de seis meses e contas em aberto/vencidas.
- Links de WhatsApp e exportação CSV.
- Atualização manual do snapshot por subprocesso.

### Retorno/CRM

- Lista priorizada por score e buckets ALTA/MEDIA/BAIXA/OBSERVAR.
- Alertas de sete dias, pipeline de renovação, onboarding, datas e sem professor.
- Filtros por bucket, professor, modalidade, contrato, score, nome, urgência,
  saúde, origem, operador e status.
- Registro de contato com status, observação, origem e operador.
- Histórico de contatos e indicadores de eficácia.
- Tendências, gráficos agregados e exportações CSV.
- Banner sazonal automático.

### Evolução de treino

- Seleção de aluno e ficha atual.
- Sessões e exercícios com séries, repetições, carga e observações.
- Histórico de carga por exercício em modal.
- Indicadores de carga e volume por grupo muscular.
- Atualização manual dos dados.

## 3. Regras de negócio preservadas

- Ativo = cliente com pelo menos um contrato de status ativo.
- MRR = `valorTotal / tempoDuracao` para contratos com duração maior que um mês.
- Churn usa a menor data efetiva entre validade, encerramento e bloqueio.
- Modalidade é derivada do texto livre da descrição do contrato.
- Professor vem da aba `Alunos` do Controle Professores.
- Presença une `Presencas` e `PresencasManuais`.
- Registro semanal é único por aluno e início da semana.
- Retenção compara status contratual e engajamento por presença.
- O score de retorno e a frequência esperada por modalidade permanecem iguais.
- As transferências internas do NextFit Pay permanecem fora do financeiro.
- A detecção de execução de treino e suas convenções permanecem no código atual.

## 4. Dependências diretas do Streamlit

| Recurso atual | Uso | Substituição |
|---|---|---|
| `st.session_state` | login, professor, semana, filtros e modal | cookie HttpOnly assinado + estado React/URL |
| `st.cache_data` | Sheets e cálculos, TTL de 60–300 s | cache TTL no serviço backend, com invalidação após escrita |
| `st.cache_resource` | não encontrado | dependências singleton do FastAPI quando necessário |
| `st.secrets` | IDs, service account e senhas | variáveis de ambiente e JSON de credenciais |
| `st.form` | tarefa manual | formulário React validado + endpoint REST |
| `st.dialog` | evolução e contato | modal acessível no frontend |
| `st.dataframe` | tabelas | tabelas responsivas com busca, ordenação e paginação local |
| `st.altair_chart`/`st.bar_chart` | gráficos | Recharts no frontend |
| `st.download_button` | CSV | endpoints `text/csv` ou download gerado no cliente |
| `st.success/warning/error/info/toast` | feedback | sistema de alertas/toasts e estados vazios/erro |
| `st.spinner` | carregamento | skeletons e indicadores de requisição |
| `st.tabs`, sidebar e expansores | navegação | rotas reais, menu responsivo, abas e acordeões acessíveis |
| `st.rerun` | refletir alterações | invalidação de consulta e atualização do estado |

Não há `st.file_uploader` nem upload de arquivos a migrar.

## 5. Arquitetura recomendada

### Escolha

- **Backend:** FastAPI, API REST, mantendo os módulos Python atuais.
- **Frontend:** React + Vite, com rotas por produto e componentes responsivos.
- **Persistência:** Google Sheets existente; SQLite HYROX permanece separado.
- **Autenticação:** sessão assinada em cookie HttpOnly, autorização por papel
  (`admin` ou `professor`) e proteção CSRF nas operações de escrita.
- **Deploy:** contêiner único em produção, servindo a API e o build do frontend.

React é justificado pela quantidade de estados, filtros, tabelas, gráficos, modais e
rotas. Templates server-side simplificariam o build, mas recriariam no servidor o
estado interativo que hoje já é amplo e tornariam a manutenção dos cinco painéis mais
difícil.

O contêiner único evita CORS e cookies entre domínios em produção. Em desenvolvimento,
Vite usa proxy para a API.

### Compatibilidade com a Hostinger

O plano atual é **Single Web Hosting**. Ele não executa Python e não aceita este
backend. A aplicação pode usar o domínio oficial de duas formas seguras:

1. apontar `professores.ctitalovieira.com.br` para um serviço de contêiner
   (Cloud Run, Render ou VPS); ou
2. fazer upgrade para VPS Hostinger e executar o contêiner no próprio VPS.

Copiar somente o frontend para `public_html` não é suficiente porque exporia ou
eliminaria as credenciais necessárias para Google Sheets e NextFit.

## 6. Estrutura proposta

```text
backend/
  app/
    api/             # rotas REST por produto
    core/            # configuração, segurança, cache e logging
    repositories/    # acesso a Sheets e snapshots
    schemas/         # contratos Pydantic da API
    services/        # orquestração, sem regras de interface
    main.py
  tests/
frontend/
  src/
    api/
    components/
    pages/
    styles/
    App.jsx
    main.jsx
  package.json
Dockerfile
docker-compose.yml
```

Os módulos de domínio em `src/controle_professores/` continuam sendo a fonte das
regras de retenção, presença, semana, registro e treino.

## 7. Plano de migração

1. Remover `st.secrets` da camada de dados e aceitar credenciais por ambiente.
2. Criar configuração, autenticação, autorização, cache e health check do backend.
3. Expor endpoints do professor e testar isolamento por carteira.
4. Expor endpoints administrativos reaproveitando os cálculos atuais.
5. Migrar painel de segunda, CRM e evolução de treinos.
6. Criar o frontend e validar cada fluxo em desktop e mobile.
7. Substituir os atalhos locais e a inicialização por comandos web normais.
8. Remover os cinco arquivos Streamlit, `.streamlit/` e a dependência.
9. Rodar testes de equivalência, API, build e busca global por Streamlit.
10. Publicar sem alterar a planilha e só então conectar o subdomínio.

## 8. Riscos identificados

- **Hospedagem:** o plano Hostinger atual não executa FastAPI; requer serviço externo
  ou VPS.
- **Credenciais:** hoje a produção depende de `st.secrets`; a migração exige cadastrar
  as mesmas variáveis no novo ambiente sem commitá-las.
- **Senhas:** o modelo atual usa senhas compartilhadas. A nova camada melhora sessão e
  autorização, mas a troca para usuários individuais exigiria decisão de negócio.
- **Google Sheets:** não oferece transações. Escritas concorrentes precisam manter os
  upserts em lote e invalidar cache após sucesso.
- **Painéis locais:** telefone e financeiro passarão a uma aplicação online; todas as
  rotas devem exigir perfil de administrador.
- **Tarefas:** `_painel_tarefas.json` em disco não é adequado a múltiplas instâncias.
  A primeira migração preservará o formato; produção deve usar volume persistente ou
  mover essa pequena tabela para uma aba Google dedicada.
- **Atualização NextFit:** o refresh da API v2 atualmente pode alterar `.env`; em
  contêiner imutável isso precisa ser mantido fora do ciclo de requisição ou persistido
  em armazenamento seguro.
- **Código legado:** `retorno.py` e `app.py` têm regras misturadas com UI. A equivalência
  exige extrair serviços antes da remoção dos arquivos.

## 9. Linha de base de validação

- Busca inicial: cinco arquivos de interface e um cliente de dados importam Streamlit.
- Testes existentes: 25 testes HYROX aprovados com `unittest`.
- `pytest` não estava instalado no ambiente virtual no início da auditoria.
- Nenhuma alteração de dados ou de produção foi feita durante a auditoria.
