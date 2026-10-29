import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { Shell, ErrorBox } from './DailyWorkflow';
import './schedule.css';

import { days, minutes, duration, hours, monthSummary, overlaps, coverageRange } from './scheduleUtils';
const money = value => value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const currentMonth = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`; };
const coverageLabel = range => range.min === range.max ? `${range.min} ${range.min === 1 ? 'professor' : 'professores'}` : `${range.min}–${range.max} professores`;
const clock = h => `${String(h).padStart(2,'0')}:00`;

export function SchedulePage() {
  const [teachers, setTeachers] = useState([]), [users, setUsers] = useState([]);
  const [chosen, setChosen] = useState(''), [name, setName] = useState(''), [selected, setSelected] = useState('');
  const [month, setMonth] = useState(currentMonth), [error, setError] = useState(''), [usersError, setUsersError] = useState('');
  const [loadFailed, setLoadFailed] = useState(false);
  const revision = useRef(0);
  const [loading, setLoading] = useState(true), [saving, setSaving] = useState(false), [dirty, setDirty] = useState(false), [message, setMessage] = useState('');
  async function loadUsers() { try { const data = await api('/api/admin/schedule/users'); setUsers(data.users); setUsersError(''); } catch(e) { setUsersError(e.message); } }
  useEffect(() => { api('/api/admin/schedule').then(data => setTeachers(data.teachers)).catch(e => { setError(e.message); setLoadFailed(true); }).finally(() => setLoading(false)); loadUsers(); }, []);
  function change(next) { revision.current += 1; setTeachers(next); setDirty(true); setMessage(''); }
  function update(id, patch) { change(teachers.map(t => t.id === id ? {...t, ...patch} : t)); }
  function addNext() { const user = users.find(u => u.id === chosen); if (user && !teachers.some(t => t.id === `nextfit:${user.id}`)) change([...teachers, {id: `nextfit:${user.id}`, name: user.name, source:'nextfit', rate:0, shifts:[]}]); setChosen(''); }
  function addTest(e) { e.preventDefault(); if (!name.trim()) return; change([...teachers, {id:`test:${crypto.randomUUID()}`, name:name.trim(), source:'test', rate:0, shifts:[]}]); setName(''); }
  async function save() { const savedRevision = revision.current; setSaving(true); setError(''); try { const data = await api('/api/admin/schedule', {method:'PUT', body:JSON.stringify({teachers})}); if (revision.current === savedRevision) { setTeachers(data.teachers); setDirty(false); setMessage('Horários salvos.'); } else { setMessage('A versão anterior foi salva. Salve novamente as alterações recentes.'); } } catch(e) { setError(e.message); setMessage('Não foi possível salvar. Tente novamente.'); } finally { setSaving(false); } }
  const total = teachers.reduce((n,t) => n + monthSummary(t.shifts,month).total * Number(t.rate || 0) / 60, 0);
  const selectedTeacher = teachers.find(t => t.id === selected);
  function toggleSlot(day, hour) {
    if (!selectedTeacher) return;
    const start = hour * 60, end = start + 60;
    const matching = selectedTeacher.shifts.findIndex(s => s.day === day && minutes(s.start) === start && minutes(s.end) === end);
    if (matching >= 0) update(selected, {shifts: selectedTeacher.shifts.filter((_,i) => i !== matching)});
    else if (!selectedTeacher.shifts.some(s => overlaps(s,day,start,end))) update(selected, {shifts:[...selectedTeacher.shifts,{day,start:clock(hour),end:clock(hour+1)}]});
  }
  return <Shell title="Horários e salários" subtitle="Monte uma escala semanal e simule a remuneração da equipe.">
    <p className="dw-source">Selecione os profissionais cadastrados no NEXT ou inclua nomes de teste. A lista do NEXT mostra usuários ativos; confirme quais são professores. A escala e os valores são visíveis somente para a administração.</p>
    <ErrorBox error={error}/>{usersError && <div className="notice error">{usersError} <button className="button" onClick={loadUsers}>Tentar novamente</button></div>}
    {loading ? <p>Carregando horários…</p> : loadFailed ? <p>Não foi possível carregar a escala salva. Atualize a página para tentar novamente.</p> : <>
    <div className="schedule-add dw-section"><label>Adicionar usuário do NEXT<select value={chosen} onChange={e => setChosen(e.target.value)}><option value="">Selecione um usuário</option>{users.filter(u => !teachers.some(t => t.id === `nextfit:${u.id}`)).map(u => <option value={u.id} key={u.id}>{u.name}</option>)}</select></label><button className="button" disabled={!chosen} onClick={addNext}>Adicionar</button>
      <form onSubmit={addTest}><label>Professor para teste<input value={name} maxLength={120} onChange={e => setName(e.target.value)} placeholder="Nome do professor" /></label><button className="button" disabled={!name.trim()}>Incluir teste</button></form></div>
    <div className="dw-toolbar"><label>Mês da simulação<input type="month" value={month} onChange={e => setMonth(e.target.value)}/></label><strong>Total estimado: {money(total)}</strong></div>
    <p className="dw-source">Estimativa bruta: valor por hora × horas previstas no mês escolhido, contando os dias reais do calendário. A mesma escala se repete em todos os sábados. As horas de sábado já estão incluídas no total. Não inclui faltas, feriados, adicionais ou encargos. Horários devem começar e terminar no mesmo dia.</p>
    {!teachers.length && <p>Adicione um professor para começar a montar a escala.</p>}
    <section className="dw-section"><div className="dw-section-head"><div><h2>Quadro semanal da equipe</h2><p>Selecione um professor e clique nas células para adicionar ou remover horas inteiras. Para horários com minutos, use os detalhes abaixo.</p></div></div>
      <label className="schedule-picker">Professor para editar<select value={selected} onChange={e => setSelected(e.target.value)}><option value="">Selecione um professor</option>{teachers.map(t => <option value={t.id} key={t.id}>{t.name}{t.source === 'test' ? ' (teste)' : ''}</option>)}</select></label>
      <div className="schedule-grid-wrap"><table className="schedule-grid"><thead><tr><th scope="col">Horário</th>{days.map(day => <th scope="col" key={day}>{day}</th>)}</tr></thead><tbody>
      {Array.from({length:17},(_,i) => i+5).map(hour => <tr key={hour}><th scope="row">{clock(hour)}–{clock(hour+1)}</th>{days.map((day,index) => { const start=hour*60, end=start+60; const realCoverage=coverageRange(teachers,index,start,end); const testCoverage=coverageRange(teachers,index,start,end,'test'); const present=teachers.filter(t => t.shifts.some(s => overlaps(s,index,start,end))); const exact=selectedTeacher?.shifts.some(s => s.day===index && minutes(s.start)===start && minutes(s.end)===end); const partial=selectedTeacher?.shifts.some(s => overlaps(s,index,start,end)) && !exact; return <td key={day}><div className="schedule-cell"><strong className="schedule-coverage">{coverageLabel(realCoverage)}</strong>{testCoverage.max > 0 && <small className="schedule-test-coverage">+ {coverageLabel(testCoverage)} de teste</small>}{present.map(t => <span className="schedule-person" key={t.id}>{t.name}{t.source === 'test' ? ' · teste' : ''}<small>{t.shifts.filter(s => overlaps(s,index,start,end)).map(s => ` ${s.start.slice(0,5)}–${s.end.slice(0,5)}`).join(',')}</small></span>)}<button type="button" className="schedule-cell-button" disabled={!selectedTeacher || partial} onClick={() => toggleSlot(index,hour)} aria-label={`${exact ? 'Remover' : 'Adicionar'} ${selectedTeacher?.name || 'professor'}: ${day} ${clock(hour)} às ${clock(hour+1)}`} title={partial ? 'Ajuste este horário nos detalhes do professor' : ''}>{exact ? '−' : '+'}</button></div></td>; })}</tr>)}
      </tbody></table></div><p className="dw-source">A grade mostra intervalos das 5h às 22h. A contagem destaca os professores reais previstos; testes aparecem separados. Se a cobertura mudar dentro da hora, mostramos o mínimo e o máximo (ex.: 1–2). Qualquer horário salvo fora dessa faixa continua disponível nos detalhes do professor.</p></section>
    {teachers.map(t => { const weekly = t.shifts.reduce((n,s) => n + duration(s), 0), summary = monthSummary(t.shifts,month), monthly = summary.total; return <section className="dw-section schedule-card" key={t.id}>
      <div className="dw-section-head"><div><h2>{t.name}</h2><small>{t.source === 'test' ? 'Professor de teste' : 'Usuário do NEXT'}</small></div><button className="button" onClick={() => { if (window.confirm(`Remover ${t.name} desta escala?`)) change(teachers.filter(x => x.id !== t.id)); }}>Remover</button></div>
      <div className="schedule-summary"><label>Valor por hora (R$)<input type="number" min="0" max="100000" step="0.01" value={t.rate} onChange={e => update(t.id,{rate:e.target.value})}/></label><span>Por semana <strong>{hours(weekly)}</strong></span><span>No mês <strong>{hours(monthly)}</strong></span><span>Sábados no mês <strong>{summary.saturdays}</strong></span><span>Horas por sábado <strong>{hours(summary.perSaturday)}</strong></span><span>Horas de sábado no mês <strong>{hours(summary.saturdayMinutes)}</strong></span><span>Salário estimado <strong>{money(monthly * Number(t.rate || 0) / 60)}</strong></span></div>
      <details className="schedule-details"><summary>Ver e editar horários de {t.name}</summary>
      {days.map((day, index) => <div className="schedule-day" key={day}><strong>{day}</strong><div>{t.shifts.map((shift,i) => shift.day === index && <div className="schedule-shift" key={i}><label>Início<input type="time" value={shift.start.slice(0,5)} onChange={e => update(t.id,{shifts:t.shifts.map((s,j) => i === j ? {...s,start:e.target.value} : s)})}/></label><label>Fim<input type="time" value={shift.end.slice(0,5)} onChange={e => update(t.id,{shifts:t.shifts.map((s,j) => i === j ? {...s,end:e.target.value} : s)})}/></label><button className="button" aria-label={`Remover horário de ${day}`} onClick={() => update(t.id,{shifts:t.shifts.filter((_,j) => i !== j)})}>×</button></div>)}</div><button className="button" onClick={() => update(t.id,{shifts:[...t.shifts,{day:index,start:'08:00',end:'12:00'}]})}>+ Horário</button></div>)}
      </details>
    </section>; })}
    <div className="schedule-save-bar"><span role="status">{message || (dirty ? 'Alterações não salvas' : 'Horários atualizados')}</span><button className="schedule-save-button" disabled={!dirty || saving} onClick={save}>{saving ? 'Salvando…' : 'Salvar horários'}</button></div></>}
  </Shell>;
}
