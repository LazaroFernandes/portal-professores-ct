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
