import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Shell, ErrorBox } from './DailyWorkflow';
import './schedule.css';

const days = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];
const money = value => value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const minutes = value => { const [h, m] = value.split(':').map(Number); return h * 60 + m; };
const duration = shift => Math.max(0, minutes(shift.end) - minutes(shift.start));
const hours = value => `${Math.floor(value / 60)}h${String(value % 60).padStart(2, '0')}`;
const currentMonth = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`; };
function monthMinutes(shifts, month) {
  const [year, m] = month.split('-').map(Number);
  if (!year || !m) return 0;
  const totalDays = new Date(year, m, 0).getDate();
  let total = 0;
  for (let d = 1; d <= totalDays; d++) {
    const day = (new Date(year, m - 1, d).getDay() + 6) % 7;
    total += shifts.filter(s => s.day === day).reduce((n,s) => n + duration(s), 0);
  }
  return total;
}

export function SchedulePage() {
  const [teachers, setTeachers] = useState([]), [users, setUsers] = useState([]);
  const [chosen, setChosen] = useState(''), [name, setName] = useState('');
  const [month, setMonth] = useState(currentMonth), [error, setError] = useState(''), [usersError, setUsersError] = useState('');
  const [loadFailed, setLoadFailed] = useState(false);
  const [loading, setLoading] = useState(true), [saving, setSaving] = useState(false), [dirty, setDirty] = useState(false), [message, setMessage] = useState('');
  async function loadUsers() { try { const data = await api('/api/admin/schedule/users'); setUsers(data.users); setUsersError(''); } catch(e) { setUsersError(e.message); } }
  useEffect(() => { api('/api/admin/schedule').then(data => setTeachers(data.teachers)).catch(e => { setError(e.message); setLoadFailed(true); }).finally(() => setLoading(false)); loadUsers(); }, []);
  function change(next) { setTeachers(next); setDirty(true); setMessage(''); }
  function update(id, patch) { change(teachers.map(t => t.id === id ? {...t, ...patch} : t)); }
  function addNext() { const user = users.find(u => u.id === chosen); if (user && !teachers.some(t => t.id === `nextfit:${user.id}`)) change([...teachers, {id: `nextfit:${user.id}`, name: user.name, source:'nextfit', rate:0, shifts:[]}]); setChosen(''); }
  function addTest(e) { e.preventDefault(); if (!name.trim()) return; change([...teachers, {id:`test:${crypto.randomUUID()}`, name:name.trim(), source:'test', rate:0, shifts:[]}]); setName(''); }
  async function save() { setSaving(true); setError(''); try { const data = await api('/api/admin/schedule', {method:'PUT', body:JSON.stringify({teachers})}); setTeachers(data.teachers); setDirty(false); setMessage('Horários salvos.'); } catch(e) { setError(e.message); } finally { setSaving(false); } }
  const total = teachers.reduce((n,t) => n + monthMinutes(t.shifts,month) * Number(t.rate || 0) / 60, 0);
  return <Shell title="Horários e salários" subtitle="Monte uma escala semanal e simule a remuneração da equipe.">
    <p className="dw-source">Selecione os profissionais cadastrados no NEXT ou inclua nomes de teste. A lista do NEXT mostra usuários ativos; confirme quais são professores. A escala e os valores são visíveis somente para a administração.</p>
    <ErrorBox error={error}/>{usersError && <div className="notice error">{usersError} <button className="button" onClick={loadUsers}>Tentar novamente</button></div>}
    {loading ? <p>Carregando horários…</p> : loadFailed ? <p>Não foi possível carregar a escala salva. Atualize a página para tentar novamente.</p> : <>
    <div className="schedule-add dw-section"><label>Adicionar usuário do NEXT<select value={chosen} onChange={e => setChosen(e.target.value)}><option value="">Selecione um usuário</option>{users.filter(u => !teachers.some(t => t.id === `nextfit:${u.id}`)).map(u => <option value={u.id} key={u.id}>{u.name}</option>)}</select></label><button className="button" disabled={!chosen} onClick={addNext}>Adicionar</button>
      <form onSubmit={addTest}><label>Professor para teste<input value={name} maxLength={120} onChange={e => setName(e.target.value)} placeholder="Nome do professor" /></label><button className="button" disabled={!name.trim()}>Incluir teste</button></form></div>
    <div className="dw-toolbar"><label>Mês da simulação<input type="month" value={month} onChange={e => setMonth(e.target.value)}/></label><strong>Total estimado: {money(total)}</strong><button className="button" disabled={!dirty || saving} onClick={save}>{saving ? 'Salvando…' : 'Salvar horários'}</button><span role="status">{message || (dirty ? 'Alterações ainda não salvas' : '')}</span></div>
    <p className="dw-source">Estimativa bruta: valor por hora × horas previstas no mês escolhido, contando os dias reais do calendário. Não inclui faltas, feriados, adicionais ou encargos. Horários devem começar e terminar no mesmo dia.</p>
    {!teachers.length && <p>Adicione um professor para começar a montar a escala.</p>}
    {teachers.map(t => { const weekly = t.shifts.reduce((n,s) => n + duration(s), 0), monthly = monthMinutes(t.shifts,month); return <section className="dw-section schedule-card" key={t.id}>
      <div className="dw-section-head"><div><h2>{t.name}</h2><small>{t.source === 'test' ? 'Professor de teste' : 'Usuário do NEXT'}</small></div><button className="button" onClick={() => { if (window.confirm(`Remover ${t.name} desta escala?`)) change(teachers.filter(x => x.id !== t.id)); }}>Remover</button></div>
      <div className="schedule-summary"><label>Valor por hora (R$)<input type="number" min="0" max="100000" step="0.01" value={t.rate} onChange={e => update(t.id,{rate:e.target.value})}/></label><span>Por semana <strong>{hours(weekly)}</strong></span><span>No mês <strong>{hours(monthly)}</strong></span><span>Salário estimado <strong>{money(monthly * Number(t.rate || 0) / 60)}</strong></span></div>
      {days.map((day, index) => <div className="schedule-day" key={day}><strong>{day}</strong><div>{t.shifts.map((shift,i) => shift.day === index && <div className="schedule-shift" key={i}><label>Início<input type="time" value={shift.start.slice(0,5)} onChange={e => update(t.id,{shifts:t.shifts.map((s,j) => i === j ? {...s,start:e.target.value} : s)})}/></label><label>Fim<input type="time" value={shift.end.slice(0,5)} onChange={e => update(t.id,{shifts:t.shifts.map((s,j) => i === j ? {...s,end:e.target.value} : s)})}/></label><button className="button" aria-label={`Remover horário de ${day}`} onClick={() => update(t.id,{shifts:t.shifts.filter((_,j) => i !== j)})}>×</button></div>)}</div><button className="button" onClick={() => update(t.id,{shifts:[...t.shifts,{day:index,start:'08:00',end:'12:00'}]})}>+ Horário</button></div>)}
    </section>; })}</>}
  </Shell>;
}
