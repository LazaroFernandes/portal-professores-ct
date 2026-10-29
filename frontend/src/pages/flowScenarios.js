export function scenarios(cell, ratio) {
  const need = cell[`need${ratio}`];
  const available = need != null && cell.scheduled != null && cell.real_min != null;
  const deficit = count => available ? Math.max(0, need - count) : null;
  return {
    need,
    current: {min:available?cell.real_min:null, max:available?cell.real_max:null, missingMin:deficit(cell.real_max), missingMax:deficit(cell.real_min)},
    proposed: {min:available?cell.scheduled:null, max:available?cell.scheduled_max:null, missingMin:available?cell[`missing${ratio}_min`]:null, missingMax:available?cell[`missing${ratio}`]:null},
    improvement: available ? deficit(cell.real_min)-cell[`missing${ratio}`] : null,
  };
}
export function summarizeScenarios(cells, ratio) {
  const valid = cells.map(c=>scenarios(c,ratio)).filter(s=>s.current.missingMax!==null);
  return {count:valid.length, current:valid.filter(s=>s.current.missingMax>0).length, proposed:valid.filter(s=>s.proposed.missingMax>0).length, improved:valid.filter(s=>s.improvement>0).length, resolved:valid.filter(s=>s.current.missingMax>0&&s.proposed.missingMax===0).length};
}

export function coverageStatus(scenario, need) {
 if (need == null || scenario.min == null || scenario.max == null) return {state:'unknown',label:'Sem dados',detail:'Cobertura não confirmada'};
 const low=scenario.min-need, high=scenario.max-need;
 const amount=(a,b)=>a===b?`${a}`:`${a}–${b}`;
 if(low<0) return {state:'deficit',label:'▼ Faltam professores',detail:`Faltam ${amount(Math.max(0,-high),-low)} prof.${high>=0?' · varia na hora':''}`};
 if(low>0) return {state:'surplus',label:'▲ Acima do necessário',detail:`${amount(low,high)} prof. a mais`};
 if(high>0) return {state:'variable',label:'✓ OK / ▲ Acima',detail:`Até ${high} prof. a mais · varia na hora`};
 return {state:'sufficient',label:'✓ Quantidade adequada',detail:'Igual à necessidade estimada'};
}
