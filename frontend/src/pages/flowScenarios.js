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
