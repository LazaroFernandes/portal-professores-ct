# Financeiro administrativo

Rota `/admin/financeiro`, API `GET /api/admin/finance?month=AAAA-MM`.
Ambas exigem administrador. Não há escrita financeira no NextFit.

## Apuração

- Valores calculados em centavos com Decimal; repetições idênticas do mesmo ID são removidas. IDs conflitantes interrompem a consulta. Nunca excluir uma conta apenas por nome/valor iguais.
- Realizado vem exclusivamente de MovimentoFinanceiro/Efetivado, pela dataEfetivacao civil local. Coleta completa, sem filtro de criação que poderia perder liquidações posteriores.
- Contas recebidas e contas pagas não são somadas ao realizado novamente.
- Transferências internas usam o template exato `Transferência de conta Next Fit Pay para conta bancária`, método Transferencia, sem cliente/fornecedor. Um par precisa ter Entrada/Saida, IDs diferentes, mesmo timestamp integral/valor e contas diferentes. Retiram-se ambos os lados; eles permanecem disponíveis em detalhes. Grupos ambíguos são preservados e sinalizados.
- Par com contraparte aguardando efetivação é identificado separadamente. O lado efetivado continua no realizado e o pendente continua separado: a classificação não muda o dinheiro. A tela mostra os dois IDs, as situações e o efeito no saldo do mês selecionado.
- A receber: Aberto, usando saldo quando informado; Recebido, Cancelado e Renegociado ficam fora da previsão. Situações desconhecidas ficam sinalizadas.
- A pagar: Status 1 sem PagarPagamento. Status 2/3 nunca comprovam pagamento por si; o realizado vem do movimento. Pagamento parcial sem saldo inequívoco fica sinalizado, sem estimativa arbitrária.
- Repasses aguardando efetivação ficam separados, não somados às cobranças abertas: falta vínculo inequívoco entre as fontes. Vencidos ficam separados com a situação atual, sem prometer recebimento em nova data.
- Sobra/falta é fluxo do período, não lucro nem saldo bancário. Não há estimativa de despesas ainda não lançadas.

## Previsão

Base: mês anterior completo, ou último mês completo para projeção do próximo mês.
Replicar recebimentos pelos dias civis futuros equivalentes, incluindo as matrículas/renovações que compõem o histórico, sem supor crescimento. Em cada faixa semanal, estimativa adicional = máximo(0, histórico futuro - cobranças abertas). Somar realizado + abertas + estimativa. Dias já transcorridos e o dia corrente não recebem extrapolação.

A origem Contrato não identifica nova matrícula versus renovação. Não há previsão individual de novas matrículas nem acréscimo automático de meta comercial. Meses encerrados mostram somente realizado, não uma reconstrução das previsões antigas. Dias 29–31 do mês-base são reunidos no último dia quando o destino é mais curto.

## Nomes e agenda de renovações

`codigoCliente` liga movimentos/cobranças ao `id` de `Pessoa/GetClientes`; o nome é o cadastrado atualmente. Nome ausente fica explicitamente identificado pelo código do cliente, sem associação por texto ou valor.

A agenda semanal usa `ContratoCliente.dataValidade` de contratos ativos e clientes não inativos, com os nomes dos planos de `ContratoBase`. `dataRenovacao` registra evento passado e não é usada como próximo vencimento. São preservados contratos de planos paralelos; um contrato já coberto por sucessor ativo do mesmo cliente/plano, início posterior e cobertura contígua, não gera outra previsão na data antiga. Contratos encerrados/cancelados e datas já passadas não aparecem como renovação futura.

Essa agenda mostra cliente/data/plano, incluindo planos sem cobrança adicional, e não acrescenta o valor nominal dos contratos ao caixa. A projeção monetária continua histórica e agregada. Assim, uma cobrança já emitida e a agenda de renovação não duplicam receita. Nomes e agenda só estão disponíveis ao administrador, como os demais dados financeiros.

## Consulta e UX

Primeira leitura paginada executada em thread; HTTP 202 enquanto coleta. Somente snapshots completos são expostos. Cache em memória de até 15 minutos com horário visível; HTTP privado/no-store. Falha retorna 503 sem registros/segredos da origem. Histórico dos últimos 12 meses; seletor permite últimos 36 e próximo mês. Quatro faixas fixas (01–07, 08–15, 16–24, 25–fim), detalhes em dropdown nativo recolhido por padrão.

Prévia isolada: `scripts/preview_finance.py --env /caminho/Nextfit/.env`. Liga somente em 127.0.0.1, desativa scheduler, usa SQLite/sessões isolados. `.local-finance` não entra no Git nem no contexto Docker. O link privado de acesso fica em `.local-finance/access-url.txt`.

## Verificação

`PYTHONPATH=src .venv312/bin/python -m unittest backend.tests.test_finance -q`.
Casos: repetição por ID, identidade conflitante, recebimento em duas fontes, parcial, status sem pagamento, vencidos, projeção incremental, dias de fevereiro, transferência cliente versus par interno, paginação incompleta, anonimato/professor/admin, HTTP 202 e erros sanitizados.
