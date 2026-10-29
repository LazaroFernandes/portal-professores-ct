import {useState} from 'react';
import {api} from '../api/client';
import {Shell,ErrorBox} from './DailyWorkflow';
import {days} from './scheduleUtils';
import './flow.css';
import {scenarios,summarizeScenarios,coverageStatus} from './flowScenarios';
const iso=d=>{const x=new Date();x.setDate(x.getDate()+d);return `${x.getFullYear()}-${String(x.getMonth()+1).padStart(2,'0')}-${String(x.getDate()).padStart(2,'0')}`;};
const date=s=>s.split('-').reverse().join('/');
const show=n=>n===null?'—':n;
const range=(low,high)=>low==null?'—':low===high?low:`${low}–${high}`;
function ScenarioCard({label,caption,value,tone}) {
 return <article className={`flow-overview-card ${tone}`}><span>{label}</span><strong>{value}</strong><small>{caption}</small></article>;
}
function CoveragePanel({label,caption,scenario,kind,need}) {
 const status=coverageStatus(scenario,need);
 return <div className={`flow-scenario ${kind} ${status.state}`}><strong>{label}</strong><small>{caption}</small><b className="flow-count">{range(scenario.min,scenario.max)} <small>prof.</small></b><span className="flow-result">{status.label}</span><small className="flow-status-detail">{status.detail}</small></div>;
}
export function FlowPage(){
 const [start,S]=useState(()=>iso(-14)),[end,E]=useState(()=>iso(-1)),[stay,T]=useState('90'),[data,D]=useState(null),[error,X]=useState(''),[loading,L]=useState(false);
 const [ratio,R]=useState(4),[dayFilter,F]=useState('all'),[view,V]=useState('both');
 const columns=days.map((name,index)=>({name,index})).filter(d=>dayFilter==='all'||d.index===Number(dayFilter));
 const summary=data?summarizeScenarios(data.rows.flatMap(row=>columns.map(d=>row.cells[d.index])),ratio):null;
 async function load(e){e.preventDefault();D(null);X('');L(true);try{D(await api(`/api/admin/flow?start=${start}&end=${end}&stay=${stay}`));}catch(err){X(err.message);}finally{L(false);}}
 return <Shell title="Fluxo e cobertura" subtitle="Estimativa da musculação a partir dos acessos do NEXT e da escala prevista.">
 <form onSubmit={load} className="dw-toolbar"><label>De<input type="date" required value={start} max={end} onChange={e=>S(e.target.value)}/></label><label>Até<input type="date" required value={end} min={start} max={iso(-1)} onChange={e=>E(e.target.value)}/></label><label>Permanência estimada<select value={stay} onChange={e=>T(e.target.value)}><option value="90">1h30</option><option value="60">1h</option></select></label><button className="button" disabled={loading}>{loading?'Consultando NEXT…':'Consultar / atualizar'}</button></form>
 <p>Somente acessos de ACESSORIA FIXO e CONSULTORIA LIVRE. Selecione até 62 dias completos, com término até ontem.</p>
 <p className="notice">A catraca registra a entrada; ela não comprova saída nem permanência na musculação. Cada pessoa é contada uma vez por instante, mesmo com passagens repetidas. A escala prevista não comprova presença do professor.</p>
 <ErrorBox error={error}/>{loading&&<p role="status">Consultando todas as páginas de acessos. A consulta pode levar alguns minutos.</p>}
 {data&&<>
 <section className="dw-section"><h2>{date(data.start)} a {date(data.end)} · permanência de {data.stay} minutos</h2><p>Dados do NEXT consultados em {new Date(data.updated_at).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'})} (consulta reutilizada por até 5 minutos). Escala lida em {new Date(data.schedule_read_at).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'})}.</p>
 {!data.data_available&&<p className="notice error">Estimativas indisponíveis: {data.eligible_records===0?'nenhum acesso elegível foi retornado.':'há registros incompletos que impedem um cálculo confiável.'} Os traços não significam zero alunos. Registros inválidos: {data.invalid_records}; sem modalidade: {data.unclassified_records}.</p>}
 {data.unclassified_records>0&&<p className="notice error">{data.unclassified_records} acesso(s) sem modalidade foram excluídos. As estimativas podem estar subestimadas; os zeros representam ausência de entradas elegíveis retornadas, não confirmação de academia vazia.</p>}
 {!data.schedule_available&&<p className="notice error">Não há turnos cadastrados na escala, incluindo os de teste. A cobertura e as faltas estão indisponíveis.</p>}
 <details className="flow-method"><summary>Como os cenários são calculados e limitações</summary><p>Cada linha considera toda a faixa indicada, por exemplo 05:00–06:00. A média pondera o tempo de permanência de cada aluno durante a hora, com precisão de segundos. Entradas e inícios são incluídos; saídas estimadas e fins de turno são excluídos.</p>
 <p>Média = total de aluno-minutos na faixa ÷ 60 ÷ datas do respectivo dia. Necessidade = média ÷ 4 ou ÷ 3, arredondada para cima, como referência constante para a hora. A cobertura total inclui professores do NEXT e professores de teste, conforme os horários salvos. Mostramos o mínimo e o máximo de professores simultâneos dentro da faixa. Os testes estão identificados e também reduzem as faltas; esse cenário é uma simulação e não confirma contratação ou presença. A falta varia conforme as trocas de turno: necessidade menos cobertura total em cada trecho, com mínimo zero. O destaque considera a maior falta na hora. O pico é a maior ocupação estimada em qualquer instante da faixa, entre todas as datas; pode superar bastante a média.</p>
 <details><summary>Datas e dias analisados</summary>{days.map((day,i)=><p key={day}><b>{day}: {data.dates[i].length} dia(s)</b> · {data.dates[i].map(date).join(', ')||'Nenhuma data no período'}</p>)}</details>
 <p className="dw-source">Todos os dias do período entram no denominador, inclusive datas sem passagens retornadas. O NEXT não fornece prova de funcionamento integral da catraca: ausência de registros pode indicar ausência de entradas ou falha de coleta. Não há comprovação independente de completude. A classificação usa a modalidade registrada no acesso. A escala semanal atual é aplicada ao período inteiro; não há histórico de alterações da escala.</p></details></section>
 <div className="flow-comparison-controls">
 <label>Referência de atendimento<select value={ratio} onChange={e=>R(Number(e.target.value))}><option value={4}>Até 4 alunos por professor</option><option value={3}>Cerca de 3 alunos por professor</option></select></label>
 <label>Dia da semana<select value={dayFilter} onChange={e=>F(e.target.value)}><option value="all">Semana completa</option>{days.map((day,i)=><option key={day} value={i}>{day}</option>)}</select></label>
 <div className="flow-view-switch" role="group" aria-label="Visualização dos cenários">{[['both','Comparar'],['current','Atual'],['proposed','Novo com testes']].map(([value,label])=><button className={view===value?'active':''} aria-pressed={view===value} key={value} onClick={()=>V(value)}>{label}</button>)}</div>
 </div>
 <div className="flow-overview">
 <ScenarioCard label="ATUAL · somente NEXT" value={summary.count?summary.current:'—'} caption="faixas com falta de professores" tone="current"/>
 <ScenarioCard label="NOVO · NEXT + testes" value={summary.count?summary.proposed:'—'} caption="faixas ainda com falta" tone="proposed"/>
 <ScenarioCard label="IMPACTO DA SIMULAÇÃO" value={summary.count?summary.resolved:'—'} caption={`faixas com falta zerada · ${summary.improved} melhoradas no total`} tone="impact"/>
 </div>
 <p className="flow-legend">Comparação de {summary.count} faixas dia/horário com dados nos filtros. Os estados comparam a escala com a necessidade estimada na referência selecionada. Se houver falta em qualquer trecho da hora, o alerta vermelho tem prioridade. Os mesmos alunos e a mesma necessidade são usados nos dois cenários. Testes representam simulação de escala, não presença efetiva.</p>
 <div className="flow-status-legend" aria-label="Legenda da cobertura"><span className="deficit">▼ Faltam professores</span><span className="sufficient">✓ Quantidade adequada</span><span className="surplus">▲ Acima do necessário</span><span className="variable">✓ OK / ▲ Acima · varia na hora</span></div>
 <div className="flow-table-wrap"><table className={`flow-table flow-comparison-table ${columns.length===1?'flow-table-single':''}`}><thead><tr><th>Faixa</th>{columns.map(({name,index})=><th key={name}>{name}<small>{data.dates[index].length} dia(s)</small></th>)}</tr></thead><tbody>{data.rows.map(row=><tr key={row.time}><th scope="row">{row.label}</th>{columns.map(({index})=>{const c=row.cells[index],s=scenarios(c,ratio);return <td key={index}>
 <div className="flow-demand"><strong>{c.mean===null?'—':c.mean.toLocaleString('pt-BR',{maximumFractionDigits:2})}</strong><span>alunos simultâneos em média</span><b>Precisa: {show(s.need)} prof.</b></div>
 <div className={`flow-scenarios ${view!=='both'?'single':''}`}>
 {view!=='proposed'&&<CoveragePanel label="ATUAL" caption="Somente NEXT" scenario={s.current} need={s.need} kind="current"/>}
 {view!=='current'&&<CoveragePanel label="NOVO" caption="NEXT + testes" scenario={s.proposed} need={s.need} kind="proposed"/>}
 </div>
 {c.test>0&&<span className="flow-test-badge">+ {range(c.test_min,c.test)} de teste no novo cenário</span>}
 {s.improvement>0&&<span className="flow-improvement">↓ {s.improvement} a menos na maior falta da faixa</span>}
 <details><summary>Pico e detalhes</summary><span>Pico: {show(c.peak)} alunos · {c.days} dia(s)</span><span>Referência: {ratio} alunos/professor</span><span>As faixas indicam o mínimo e o máximo dentro da hora. Médias podem esconder picos de demanda.</span></details>
 </td>;})}</tr>)}</tbody></table></div>
 </>}
 </Shell>;
}
