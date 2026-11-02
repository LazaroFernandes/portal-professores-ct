import {minutes} from './scheduleUtils';
export function replicationPlan(shifts, source, targets, mode='keep') {
 const original=shifts.filter(s=>s.day===source).sort((a,b)=>minutes(a.start)-minutes(b.start));
 if(!original.length) throw new Error('Cadastre pelo menos um turno no dia de origem.');
 const validTime=value=>/^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$/.test(value);
 if(original.some((s,i)=>!validTime(s.start)||!validTime(s.end)||minutes(s.start)>=minutes(s.end)||(i>0&&minutes(original[i-1].end)>minutes(s.start)))) throw new Error('Corrija os horários do dia de origem: início e fim válidos, sem sobreposição.');
 const selected=[...new Set(targets)].filter(d=>Number.isInteger(d)&&d>=0&&d<7&&d!==source);
 if(!selected.length) throw new Error('Selecione pelo menos um dia de destino.');
 const skipped=selected.filter(d=>mode!=='replace'&&shifts.some(s=>s.day===d));
 const applied=selected.filter(d=>!skipped.includes(d));
 const replaced=applied.filter(d=>shifts.some(s=>s.day===d));
 return {applied,skipped,replaced,original,shifts:[...shifts.filter(s=>!applied.includes(s.day)),...applied.flatMap(day=>original.map(s=>({...s,day}))) ]};
}
