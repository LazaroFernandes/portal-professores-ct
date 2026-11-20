import {useEffect,useRef,useState} from 'react';
import {Link} from 'react-router-dom';
import {api} from '../api/client';
import {Shell,ErrorBox} from './DailyWorkflow';
import {ReplicateSchedule} from './ReplicateSchedule.jsx';
import {days,coverageRange,duration,hours} from './scheduleUtils';
import {simulationTeam,simulationError} from './simulationUtils';
import './schedule.css';
import './simulation.css';
const clock=h=>`${String(h).padStart(2,'0')}:00`;
const range=r=>r.min===r.max?String(r.min):`${r.min}–${r.max}`;
const dayShifts=(shifts,day)=>shifts.filter(s=>s.day===day).map(s=>`${s.start.slice(0,5)}–${s.end.slice(0,5)}`).join(' e ')||'Sem turno';
export function SimulationPage() {
 const [teachers,T]=useState([]),[changes,C]=useState({}),[selected,S]=useState(''),[dayFilter,F]=useState('all');
 const [loading,L]=useState(true),[failed,B]=useState(false),[error,E]=useState(''),[dirty,D]=useState(false),[saving,V]=useState(false),[message,M]=useState(''),[stamp,A]=useState(null),[ignored,I]=useState(0);
 const revision=useRef(0);
 useEffect(()=>{let active=true;Promise.all([api('/api/admin/schedule'),api('/api/admin/schedule/simulation')]).then(([schedule,sim])=>{if(!active)return;T(schedule.teachers);S(schedule.teachers[0]?.id||'');const ids=new Set(schedule.teachers.map(t=>t.id));C(Object.fromEntries(sim.overrides.filter(o=>ids.has(o.teacher_id)).map(o=>[o.teacher_id,o.shifts])));I(sim.overrides.filter(o=>!ids.has(o.teacher_id)).length);A(sim.updated_at);}).catch(e=>{if(active){E(e.message);B(true);}}).finally(()=>{if(active)L(false);});return()=>{active=false;};},[]);
 useEffect(()=>{if(!dirty)return;const warn=e=>{e.preventDefault();e.returnValue='';};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[dirty]);
 function edit(next){revision.current++;C(next);D(true);M('');E('');}
 const team=simulationTeam(teachers,changes),teacher=teachers.find(t=>t.id===selected),proposed=team.find(t=>t.id===selected),validation=simulationError(changes);
 const columns=days.map((name,index)=>({name,index})).filter(d=>dayFilter==='all'||String(d.index)===dayFilter);
 const configured=teachers.some(t=>t.shifts.length)||Object.keys(changes).length>0;
 const patch=shifts=>edit({...changes,[selected]:shifts});
 function restore(){const next={...changes};delete next[selected];edit(next);}
 async function save(){if(validation){E(validation);return;}const version=revision.current;V(true);E('');try{const result=await api('/api/admin/schedule/simulation',{method:'PUT',body:JSON.stringify({overrides:Object.entries(changes).map(([teacher_id,shifts])=>({teacher_id,shifts}))})});A(result.updated_at);I(0);if(revision.current===version){D(false);M('Simulação salva. Abra o Fluxo e consulte o período para comparar a demanda.');}else M('A versão anterior foi salva. Salve novamente os ajustes recentes.');}catch(e){E(e.message);}finally{V(false);}}
 return <Shell title="Simulação de horários" subtitle="Teste novos turnos e compare a cobertura antes de mudar a escala oficial.">
 <p className="notice">O cenário atual usa a escala de Horários e salários, sem os testes. O novo cenário usa os ajustes desta tela mais os professores de teste. Salvar aqui altera somente a simulação; não muda a escala oficial nem os salários.</p>
 <ErrorBox error={error}/>{loading?<p>Carregando escala e simulação…</p>:failed?<p>Não foi possível carregar. Atualize a página antes de editar.</p>:<>
 <p>{stamp?`Última simulação salva em ${new Date(stamp).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'})}.`:'Nenhuma simulação salva ainda.'} {Object.keys(changes).length} professor(es) com ajuste. Os demais acompanham a escala oficial atual.</p>
 {ignored>0&&<p className="notice error">{ignored} ajuste(s) de professores removidos foram ignorados. Ao salvar, a simulação manterá somente os professores disponíveis.</p>}
 {!teachers.length?<p>Cadastre professores em <Link to="/admin/horarios">Horários e salários</Link> para começar.</p>:<>
 <section className="dw-section simulation-editor"><h2>Ajustar professor</h2>
 <label>Professor para simular<select value={selected} onChange={e=>S(e.target.value)}>{teachers.map(t=><option key={t.id} value={t.id}>{t.name}{t.source==='test'?' · TESTE':''}{Object.hasOwn(changes,t.id)?' · ajustado':''}</option>)}</select></label>
 {teacher&&<><p><b>{teacher.name}{teacher.source==='test'?' · Professor de teste':''}</b> · {Object.hasOwn(changes,selected)?'Turnos ajustados no novo cenário':'Usando a escala oficial'}.</p>
 <div className="simulation-hours"><span>Escala cadastrada: <b>{hours(teacher.shifts.reduce((n,s)=>n+duration(s),0))}/semana</b></span><span>Novo cenário: <b>{validation?'Revise os turnos':`${hours(proposed.shifts.reduce((n,s)=>n+duration(s),0))}/semana`}</b></span></div>
 <div className="simulation-actions"><button className="button" disabled={!Object.hasOwn(changes,selected)} onClick={restore}>Voltar à escala oficial deste professor</button><button className="button" onClick={()=>{if(window.confirm(`Retirar todos os turnos de ${teacher.name} somente na simulação?`))patch([]);}}>Simular sem turnos</button></div>
 <ReplicateSchedule teacher={proposed} onApply={patch} saveLabel="Salvar simulação"/>
 <p>Edite o início e o fim, inclusive os minutos. Cada ajuste substitui a semana inteira deste professor somente no cenário novo.</p>
 {days.map((day,index)=><div className="simulation-day" key={day}><div><strong>{day}</strong><small>Escala cadastrada: {dayShifts(teacher.shifts,index)}</small></div><div>{proposed.shifts.map((shift,i)=>shift.day===index&&<div className="schedule-shift" key={i}><label>Início · {day}<input type="time" value={shift.start.slice(0,5)} onChange={e=>patch(proposed.shifts.map((s,j)=>i===j?{...s,start:e.target.value}:s))}/></label><label>Fim · {day}<input type="time" value={shift.end.slice(0,5)} onChange={e=>patch(proposed.shifts.map((s,j)=>i===j?{...s,end:e.target.value}:s))}/></label><button className="button" aria-label={`Remover turno de ${day}`} onClick={()=>patch(proposed.shifts.filter((_,j)=>i!==j))}>×</button></div>)}</div><button className="button" onClick={()=>patch([...proposed.shifts,{day:index,start:'08:00',end:'12:00'}])}>+ Turno · {day}</button></div>)}
 </>}
 </section>
 <section className="dw-section"><h2>Cobertura por hora · prévia imediata</h2><p>Esta tabela já considera os ajustes em edição. Para saber se faltam professores em relação aos alunos, salve a simulação e consulte o Fluxo.</p>
 <label>Dia para comparar<select value={dayFilter} onChange={e=>F(e.target.value)}><option value="all">Semana completa</option>{days.map((d,i)=><option value={i} key={d}>{d}</option>)}</select></label>
 {validation?<p role="alert" className="notice error">{validation}</p>:!configured?<p className="notice">Nenhuma escala preenchida. Cadastre turnos para comparar; ausência de dados não significa zero professores.</p>:<div className="simulation-table-wrap"><table className={`simulation-table ${columns.length===1?'single':''}`}><thead><tr><th>Faixa</th>{columns.map(d=><th key={d.index}>{d.name}</th>)}</tr></thead><tbody>{Array.from({length:17},(_,i)=>i+5).map(hour=><tr key={hour}><th scope="row">{clock(hour)}–{clock(hour+1)}</th>{columns.map(d=>{const actual=coverageRange(teachers,d.index,hour*60,(hour+1)*60,'nextfit'),next=coverageRange(team,d.index,hour*60,(hour+1)*60,null),tests=coverageRange(team,d.index,hour*60,(hour+1)*60,'test');return <td key={d.index}><span>Atual <b>{range(actual)} prof.</b></span><span className="simulation-new">Novo <b>{range(next)} prof.</b></span>{tests.max>0&&<small>Inclui {range(tests)} de teste</small>}</td>;})}</tr>)}</tbody></table></div>}
 <p className="dw-source">Atual = professores reais. Novo = horários ajustados + testes. Faixas como 1–2 indicam mudanças dentro da hora, respeitando os minutos dos turnos. Quantidade prevista não comprova presença efetiva. A grade mostra 05h–22h; os turnos completos continuam no editor.</p>
 </section>
 </>}
 <div className="schedule-save-bar simulation-save"><span role="status">{message||(dirty?'Ajustes não salvos; ainda não entram no Fluxo.':'Simulação pronta para consulta.')}</span><button className="schedule-save-button" disabled={saving||!!validation||(!dirty&&!ignored)} onClick={save}>{saving?'Salvando…':'Salvar simulação'}</button>{dirty||saving?<span>Salve para comparar no Fluxo</span>:<Link className="button" to="/admin/fluxo">Abrir Fluxo e comparar demanda</Link>}</div>
 </>}
 </Shell>;
}
