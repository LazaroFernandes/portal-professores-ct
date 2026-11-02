import {useState} from 'react';
import {days} from './scheduleUtils';
import {replicationPlan} from './replicateSchedule';
export function ReplicateSchedule({teacher,onApply}) {
 const [open,setOpen]=useState(false),[source,setSource]=useState(0),[targets,setTargets]=useState([1,2,3,4]),[mode,setMode]=useState('keep'),[done,setDone]=useState('');
 let plan,error;
 try {plan=replicationPlan(teacher.shifts,source,targets,mode);} catch(e) {error=e.message;}
 const names=values=>values.map(d=>days[d]).join(', ');
 return <div className="schedule-replicate">
 <button type="button" className="button" aria-expanded={open} onClick={()=>{setOpen(!open);setDone('');}}>Replicar horários</button>
 {done&&<p role="status">{done}</p>}
 {open&&<div className="schedule-replicate-panel">
 <h3>Replicar horários de {teacher.name}{teacher.source==='test'?' (teste)':''}</h3>
 <label>Dia de origem<select value={source} onChange={e=>setSource(Number(e.target.value))}>{days.map((d,i)=><option key={d} value={i}>{d}</option>)}</select></label>
 <fieldset><legend>Dias de destino</legend><div className="schedule-replicate-shortcuts"><button type="button" className="button" onClick={()=>setTargets([0,1,2,3,4].filter(d=>d!==source))}>Segunda a sexta</button><button type="button" className="button" onClick={()=>setTargets([0,1,2,3,4,5,6].filter(d=>d!==source))}>Semana inteira</button></div>
 <div className="schedule-replicate-days">{days.map((d,i)=><label key={d}><input type="checkbox" disabled={i===source} checked={i!==source&&targets.includes(i)} onChange={e=>setTargets(e.target.checked?[...targets,i]:targets.filter(x=>x!==i))}/>{d}{i===source?' (origem)':''}</label>)}</div></fieldset>
 <label>Se o destino já tiver horários<select value={mode} onChange={e=>setMode(e.target.value)}><option value="keep">Manter os existentes (pular esse dia)</option><option value="replace">Substituir pelos horários copiados</option></select></label>
 <div className="schedule-replicate-preview" aria-live="polite"><strong>Prévia</strong>{error?<p>{error}</p>:<><p>{days[source]}: {plan.original.map(s=>`${s.start.slice(0,5)}–${s.end.slice(0,5)}`).join(' e ')}</p><p>Copiar para: {names(plan.applied)||'nenhum dia'}.</p>{plan.skipped.length>0&&<p>Manter sem alterações: {names(plan.skipped)}.</p>}{plan.replaced.length>0&&<p>Os turnos existentes serão substituídos em: <b>{names(plan.replaced)}</b>.</p>}</>}</div>
 <p>Todos os turnos e intervalos serão copiados. Depois de aplicar, clique em <b>Salvar horários</b> para gravar a escala.</p>
 <div className="schedule-replicate-shortcuts"><button type="button" className="button" disabled={!plan?.applied.length} onClick={()=>{onApply(plan.shifts);setDone(`Horários replicados para ${names(plan.applied)}. Clique em Salvar horários para gravar.`);setOpen(false);}}>Aplicar aos dias selecionados</button><button type="button" className="button" onClick={()=>setOpen(false)}>Cancelar</button></div>
 </div>}
 </div>;
}
