import {minutes} from './scheduleUtils';
export function simulationTeam(teachers, changes) {
 return teachers.map(t=>({...t,shifts:Object.hasOwn(changes,t.id)?changes[t.id]:t.shifts}));
}
export function simulationError(changes) {
 const valid=v=>/^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$/.test(v);
 for(const shifts of Object.values(changes)) {
  if(shifts.some(s=>!valid(s.start)||!valid(s.end)||minutes(s.start)>=minutes(s.end))) return 'Preencha início e fim válidos; o fim deve ser posterior ao início.';
  for(let day=0;day<7;day++) {
   const ordered=shifts.filter(s=>s.day===day).sort((a,b)=>minutes(a.start)-minutes(b.start));
   if(ordered.some((s,i)=>i>0&&minutes(ordered[i-1].end)>minutes(s.start))) return 'Há turnos sobrepostos na simulação. Ajuste os horários antes de comparar ou salvar.';
  }
 }
 return '';
}
