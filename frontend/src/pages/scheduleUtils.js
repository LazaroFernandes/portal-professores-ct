export const days = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];
export const minutes = value => { const [h, m] = String(value || '').split(':').map(Number); return Number.isFinite(h) && Number.isFinite(m) ? h * 60 + m : 0; };
export const duration = shift => Math.max(0, minutes(shift.end) - minutes(shift.start));
export const hours = value => `${Math.floor(value / 60)}h${String(value % 60).padStart(2, '0')}`;
export function monthSummary(shifts, month) {
  const [year, m] = String(month).split('-').map(Number);
  if (!year || m < 1 || m > 12) return {total:0, saturdays:0, saturdayMinutes:0, perSaturday:0};
  const perSaturday = shifts.filter(s => s.day === 5).reduce((sum,s) => sum + duration(s), 0);
  let total = 0, saturdays = 0;
  for (let date = 1; date <= new Date(year,m,0).getDate(); date++) {
    const day = (new Date(year,m-1,date).getDay()+6)%7;
    if (day === 5) saturdays++;
    total += shifts.filter(s => s.day === day).reduce((sum,s) => sum + duration(s), 0);
  }
  return {total, saturdays, saturdayMinutes:perSaturday*saturdays, perSaturday};
}
export const overlaps = (shift, day, start, end) => shift.day === day && minutes(shift.start) < end && minutes(shift.end) > start;

// Minimum and maximum simultaneous coverage within an hour, including minute changes.
export function coverageRange(teachers, day, start, end, source = 'nextfit') {
  const team = teachers.filter(t => t.source === source);
  const boundaries = new Set([start, end]);
  for (const t of team) for (const shift of t.shifts) {
    if (shift.day !== day) continue;
    for (const value of [minutes(shift.start), minutes(shift.end)]) if (start < value && value < end) boundaries.add(value);
  }
  const samples = [...boundaries].sort((a,b) => a-b).slice(0,-1);
  const counts = samples.map(point => team.filter(t => t.shifts.some(s => s.day === day && minutes(s.start) <= point && point < minutes(s.end))).length);
  return {min:Math.min(...counts), max:Math.max(...counts)};
}
