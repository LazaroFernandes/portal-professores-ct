import { useEffect, useState } from 'react';
import { LogOut, RefreshCw, ChevronDown } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { AdminNav } from '../components/AdminNav';
import { Loading, ErrorState } from '../components/AsyncState';
import { Kpi, KpiGrid } from '../components/Kpi';
import './finance.css';

const money = value => ((value || 0) / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const monthLabel = value => new Date(`${value}-02T12:00:00Z`).toLocaleDateString('pt-BR', { month: 'long', year: 'numeric', timeZone: 'UTC' });
const dayLabel = value => value.slice(8,10) + '/' + value.slice(5,7);
const currentMonth = () => new Intl.DateTimeFormat('sv-SE', {timeZone:'America/Sao_Paulo'}).format(new Date()).slice(0,7);
const statusLabel = { actual:'Realizado', open:'Em aberto', settlement:'Aguardando efetivação', internal:'Transferência interna conciliada' };
const issueLabels = {missing_date:'Sem data válida',negative_amount:'Valor negativo a conferir',unknown_movement_type:'Tipo de movimento não classificado',other_movement_status:'Situação de movimento não classificada',unknown_receivable_status:'Contas a receber em situação não classificada',unresolved_receivable_balance:'Saldo a receber não confirmado',unknown_payable_status:'Situação de despesa não classificada',unresolved_payable_balance:'Saldo a pagar não confirmado',unmatched_internal_transfer:'Transferência interna sem par único'};

function Transactions({ rows, direction }) {
  const items = rows.filter(row => row.direction === direction);
  return <section className="finance-transactions"><h3>{direction === 'in' ? 'Entradas' : 'Saídas'}</h3>
    {!items.length ? <p>Nenhum lançamento neste período.</p> : items.map(row => <div className="finance-transaction" key={row.id}>
      <div><strong>{row.label}</strong><small>{dayLabel(row.date)} · {statusLabel[row.state]} · {row.source} #{row.id.split(':')[1]}</small></div><b>{money(row.amount)}</b>
    </div>)}
  </section>;
}

export function FinancePage() {
  const { logout } = useAuth();
  const [month, setMonth] = useState(currentMonth);
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState({loading:true, data:null, error:null});
  useEffect(() => {
    const controller = new AbortController();
    let timer;
    setState({loading:true, data:null, error:null});
    function load() {
      api(`/api/admin/finance?month=${month}`, {signal:controller.signal}).then(data => {
        if (controller.signal.aborted) return;
        if (data.loading) { timer = setTimeout(load, 3000); return; }
        setState({loading:false,data,error:null});
      }).catch(error => {if (!controller.signal.aborted) setState({loading:false,data:null,error});});
    }
    load();
    return () => {controller.abort();clearTimeout(timer);};
  }, [month, revision]);
  const {loading, error, data} = state;
  const s = data?.summary;
  const balance = s ? s.projected_in-s.projected_out : 0;
  const overdueIn = data?.overdue.filter(r=>r.direction==='in').reduce((a,r)=>a+r.amount,0) || 0;
  const overdueOut = data?.overdue.filter(r=>r.direction==='out').reduce((a,r)=>a+r.amount,0) || 0;
  return <div className="page finance-page">
    <AdminNav />
    <header className="page-heading"><div><span className="eyebrow">GESTÃO FINANCEIRA</span><h1>Seu caixa, semana a semana.</h1><p>Contas, entradas e projeção em uma única visão.</p></div>
      <div className="frequency-actions"><button className="button ghost" onClick={logout}><LogOut size={17}/>Sair</button><button className="button primary" disabled={loading} onClick={()=>setRevision(v=>v+1)}><RefreshCw size={17}/>Consultar</button></div></header>
    <section className="finance-toolbar"><label>Mês de referência<input aria-label="Mês de referência" type="month" value={month} onChange={e=>{if(e.target.value)setMonth(e.target.value);}} /></label>
      <p>{data ? `${data.closed?'Mês encerrado · realizado':'Mês aberto · realizado + previsão'} · API NextFit` : 'Consulta financeira somente leitura'}</p></section>
    {loading ? <Loading label="Conferindo movimentos, recebimentos e contas no NextFit. A primeira consulta pode levar alguns minutos…"/> : error ? <ErrorState error={error} retry={()=>setRevision(v=>v+1)} /> : data && <>
      {Object.keys(data.quality.issues).length > 0 && <div className="notice warning" role="status">Há lançamentos na base que precisam de conferência. Veja os critérios abaixo: saldos não confirmados ficam separados; transferências sem par único permanecem nos totais.</div>}
      <KpiGrid><Kpi label="Entradas realizadas" value={money(s.actual_in)} detail="Movimentos efetivados"/>
        <Kpi label={data.closed?'Entradas do mês':'Entradas projetadas'} value={money(s.projected_in)} detail={`${money(s.open_in)} em aberto · ${money(s.estimate)} estimados`}/>
        <Kpi label={data.closed?'Saídas do mês':'Saídas previstas'} value={money(s.projected_out)} detail={`${money(s.actual_out)} realizados · ${money(s.open_out)} a pagar`}/>
        <Kpi label={data.closed?'Saldo do período':'Saldo projetado'} value={money(balance)} tone={balance>=0?'good':'warning'} detail="Sem saldo bancário inicial; não é lucro"/></KpiGrid>
      <section className="finance-baseline"><div><span className="eyebrow">BASE DA PREVISÃO</span><h2>{monthLabel(data.baseline.month)}</h2><strong>{money(data.baseline.amount)} recebidos</strong></div><p>O histórico de recebimentos contratuais serve como base, incluindo matrículas e renovações já pagas. A estimativa usa os dias futuros equivalentes do mês-base e desconta as cobranças abertas previstas. Novas matrículas não são identificadas separadamente pela API financeira.</p></section>
      <div className="finance-section-heading"><div><h2>Comparação semanal</h2><p>Abra uma semana para consultar os lançamentos. Períodos fixos: 01–07, 08–15, 16–24 e 25–fim.</p></div></div>
      <div className="finance-column-titles"><span>Contas e despesas</span><span>Entradas de caixa</span><span>Sobra ou falta</span></div>
      <div className="finance-weeks" key={month}>{data.weeks.map(w=>{
        const net=w.projected_in-w.projected_out;
        return <details className="finance-week" key={w.id}><summary><div className="finance-week-title"><span>SEMANA {w.id} · {dayLabel(w.start)}–{dayLabel(w.end)}</span><span className="finance-expand">Detalhes <ChevronDown size={17}/></span></div><div className="finance-week-values">
          <div><small>Saídas</small><strong>{money(w.projected_out)}</strong><span>{money(w.open_out)} a pagar</span></div>
          <div><small>Entradas</small><strong>{money(w.projected_in)}</strong><span>{money(w.actual_in)} realizados · {money(w.estimate)} estimados</span></div>
          <div className={net>=0?'finance-positive':'finance-negative'}><small>{net>=0?'Sobra de caixa':'Falta de caixa'}</small><strong>{money(net)}</strong><span>{data.closed?'Realizado':'Realizado + previsto'}</span></div>
        </div></summary><div className="finance-week-content"><div className="finance-detail-grid"><Transactions rows={w.rows} direction="out"/><Transactions rows={w.rows} direction="in"/></div>
          {w.estimate>0 && <div className="finance-estimate"><strong>Estimativa histórica adicional: {money(w.estimate)}</strong><p>Não é uma cobrança emitida nem uma matrícula confirmada. Saldo sem essa estimativa: {money(net-w.estimate)}.</p></div>}
        </div></details>;
      })}</div>
      <section className="finance-history"><h2>Retroativo mês a mês</h2><p>Valores realizados por data de efetivação. Clique para abrir um mês.</p><div className="finance-history-grid">{data.history.map(h=><button type="button" className={h.month===month?'selected':''} aria-pressed={h.month===month} key={h.month} onClick={()=>setMonth(h.month)}><strong>{monthLabel(h.month)}</strong><small>{h.closed?'Encerrado':'Em andamento'}</small><span>Entradas <b>{money(h.in)}</b></span><span>Saídas <b>{money(h.out)}</b></span><span className={h.in>=h.out?'finance-positive':'finance-negative'}>Saldo <b>{money(h.in-h.out)}</b></span></button>)}</div></section>
      <details className="finance-extra"><summary>Contas vencidas ainda abertas · receber {money(overdueIn)} · pagar {money(overdueOut)}</summary><p>Situação atual, inclusive ao consultar meses anteriores. Não foram transferidas automaticamente para a previsão desta semana.</p><div className="finance-detail-grid"><Transactions rows={data.overdue} direction="out"/><Transactions rows={data.overdue} direction="in"/></div></details>
      <details className="finance-extra"><summary>Repasses aguardando efetivação · {data.settlements.length} lançamentos</summary><p>Fora do realizado e dos totais previstos, pois a API não oferece vínculo seguro para descartar sobreposição com cobranças abertas. A data abaixo é a movimentação de origem, não promessa de repasse.</p><div className="finance-detail-grid"><Transactions rows={data.settlements} direction="out"/><Transactions rows={data.settlements} direction="in"/></div></details>
      <details className="finance-extra"><summary>Conferência dos pagamentos e critérios da apuração</summary><ul>
        <li>Realizado: somente MovimentoFinanceiro efetivado, uma vez por ID, pela data de efetivação. Contas recebidas e pagas não são somadas novamente.</li>
        <li>Contas a pagar: status 1, sem pagamento registrado. Status 2/3 não são prova de pagamento; suas despesas realizadas são lidas exclusivamente no caixa.</li>
        <li>Contas com nomes ou valores iguais são preservadas. Somente repetições do mesmo ID são removidas.</li>
        <li>Transferências internas padronizadas do NextFit Pay são retiradas das entradas e despesas apenas quando há um par único de entrada e saída, com mesmo valor e horário exato, entre contas diferentes. Outras transferências permanecem nos totais.</li>
        <li>Despesas futuras não lançadas não são estimadas. Meses anteriores mostram caixa realizado, não uma reconstrução da previsão antiga.</li>
      </ul><p>Registros consultados: {data.quality.source_counts.movements} movimentos · {data.quality.source_counts.receivables} contas a receber · {data.quality.source_counts.payables} contas a pagar. IDs repetidos removidos: {data.quality.duplicate_ids_removed}.</p>
      <p>Situações das contas a pagar na origem: {Object.entries(data.quality.payables_status_counts).map(([key,count])=>`${key}: ${count}`).join(' · ')}.</p>
      <p>Transferências internas conciliadas em toda a base: {data.quality.internal_transfer_pairs || 0} pares.</p>
      {Object.keys(data.quality.issues).length>0 && <p>Pendências da origem: {Object.entries(data.quality.issues).map(([key,count])=>`${issueLabels[key] || 'Conferência necessária'}: ${count}`).join(' · ')}.</p>}</details>
      <details className="finance-extra"><summary>Transferências internas separadas do caixa · {(data.internal_transfers || []).length} lançamentos no mês</summary><div className="finance-detail-grid"><Transactions rows={data.internal_transfers || []} direction="out"/><Transactions rows={data.internal_transfers || []} direction="in"/></div></details>
      <footer className="analysis-footnote">Fonte: API NextFit · Consulta completa em {new Date(data.read_at).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'})}. Reutilização da consulta por até 15 minutos. Valores em reais. A projeção não garante recebimentos.</footer>
    </>}
  </div>;
}
