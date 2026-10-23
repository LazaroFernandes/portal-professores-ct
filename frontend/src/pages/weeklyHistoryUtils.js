import { normalized } from './professorAnalysisUtils';

export function weekEnd(start) {
  const date = new Date(`${start}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 6);
  return date.toISOString().slice(0, 10);
}

export function needsAttention(row) {
  const record = row.record;
  return row.status === 'not_observed' || Boolean(record?.follow_up || record?.pain === 'yes'
    || ['adapted', 'interrupted'].includes(record?.outcome) || (row.legacy && row.had_pain));
}

// Keep each daily observation intact. Never infer a weekly performance rating.
export function summarizeWeek(rows, { professor = '', search = '', situation = '' } = {}) {
  const selected = rows.filter(row => (!professor || (professor === '__unassigned' ? !row.professor : row.professor === professor))
    && normalized(row.student_name).includes(normalized(search).trim()));
  const grouped = new Map();
  for (const row of selected) {
    if (!grouped.has(row.client_id)) grouped.set(row.client_id, { client_id: row.client_id, student_name: row.student_name, records: [] });
    grouped.get(row.client_id).records.push(row);
  }
  let students = [...grouped.values()].map(student => {
    const records = [...student.records].sort((a, b) => a.entered_at.localeCompare(b.entered_at));
    return { ...student, records, registered: records.filter(r => r.status === 'registered').length,
      not_observed: records.filter(r => r.status === 'not_observed').length,
      pending: records.filter(r => r.status === 'pending').length,
      attention: records.filter(needsAttention).length };
  });
  students = students.filter(s => !situation || (situation === 'pending' ? s.pending > 0 : s.attention > 0))
    .sort((a,b) => a.student_name.localeCompare(b.student_name, 'pt-BR'));
  const visible = students.flatMap(s => s.records);
  const teams = new Map();
  for (const row of visible) {
    const name = row.professor || 'Sem responsável';
    if (!teams.has(name)) teams.set(name, { name, total: 0, registered: 0, not_observed: 0, pending: 0 });
    const team = teams.get(name); team.total++; team[row.status]++;
  }
  return { students, teams: [...teams.values()].sort((a,b) => a.name.localeCompare(b.name, 'pt-BR')),
    total: visible.length, unique_students: students.length,
    registered: visible.filter(r => r.status === 'registered').length,
    not_observed: visible.filter(r => r.status === 'not_observed').length,
    pending: visible.filter(r => r.status === 'pending').length };
}
