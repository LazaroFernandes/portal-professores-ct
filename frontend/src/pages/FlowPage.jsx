import {useState} from 'react';
import {api} from '../api/client';
import {Shell,ErrorBox} from './DailyWorkflow';
import {days} from './scheduleUtils';
import './flow.css';
const iso=d=>{const x=new Date();x.setDate(x.getDate()+d);return `${x.getFullYear()}-${String(x.getMonth()+1).padStart(2,'0')}-${String(x.getDate()).padStart(2,'0')}`;};
const date=s=>s.split('-').reverse().join('/');
const show=n=>n===null?'—':n;
export function FlowPage(){
 const [start,S]=useState(()=>iso(-14)),[end,E]=useState(()=>iso(-1)),[stay,T]=useState('90'),[data,D]=useState(null),[error,X]=useState(''),[loading,L]=useState(false);
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
 {!data.schedule_available&&<p className="notice error">Não há turnos de professores reais na escala. A cobertura e as faltas estão indisponíveis. Cadastros de teste não completam a equipe real.</p>}
 <p>Retratos em cada horário indicado, com entrada e início de turno incluídos e fim excluído. A grade inclui as trocas de turno com minutos. Ela não representa a média de toda a hora; pode haver picos entre os instantes mostrados.</p>
 <p>Média = soma de alunos distintos naquele instante ÷ datas do respectivo dia. Necessidade = média ÷ 4 ou ÷ 3, arredondada para cima. Falta = necessidade menos equipe real prevista, com mínimo zero. O pico é o maior número entre as datas naquele instante.</p>
 <details><summary>Datas e dias analisados</summary>{days.map((day,i)=><p key={day}><b>{day}: {data.dates[i].length} dia(s)</b> · {data.dates[i].map(date).join(', ')||'Nenhuma data no período'}</p>)}</details>
 <p className="dw-source">Todos os dias do período entram no denominador, inclusive datas sem passagens retornadas. O NEXT não fornece prova de funcionamento integral da catraca: ausência de registros pode indicar ausência de entradas ou falha de coleta. Não há comprovação independente de completude. A classificação usa a modalidade registrada no acesso. A escala semanal atual é aplicada ao período inteiro; não há histórico de alterações da escala.</p></section>
 <div className="flow-table-wrap"><table className="flow-table"><thead><tr><th>Instante</th>{days.map((day,i)=><th key={day}>{day}<small>{data.dates[i].length} dia(s)</small></th>)}</tr></thead><tbody>{data.rows.map(row=><tr key={row.time}><th scope="row">{row.time}</th>{row.cells.map((c,i)=><td key={i} className={c.missing4>0?'flow-short':c.missing3>0?'flow-attention':''}><strong>Média: {c.mean===null?'—':c.mean.toLocaleString('pt-BR',{maximumFractionDigits:2})}</strong><span>Até 4 alunos/prof.: <b>{show(c.need4)}</b> prof.</span><span>3 alunos/prof.: <b>{show(c.need3)}</b> prof.</span><span>Escala real: <b>{show(c.scheduled)}</b></span><span>Faltam (4): <b>{show(c.missing4)}</b> · (3): <b>{show(c.missing3)}</b></span>{c.test>0&&<em>Teste: {c.test} (fora da cobertura)</em>}<details><summary>Pico e amostra</summary><span>Pico: {show(c.peak)} · {c.days} dia(s)</span></details></td>)}</tr>)}</tbody></table></div>
 </>}
 </Shell>;
}
