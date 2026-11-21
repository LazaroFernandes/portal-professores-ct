import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { Shell, ErrorBox } from './DailyWorkflow';
import './schedule.css';
import {ReplicateSchedule} from './ReplicateSchedule.jsx';

import { days, minutes, duration, hours, monthSummary, overlaps, coverageRange, withMonthlySalary, hourlyValue } from './scheduleUtils';
const money = value => value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const currentMonth = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`; };
const coverageLabel = range => range.min === range.max ? `${range.min} ${range.min === 1 ? 'professor' : 'professores'}` : `${range.min}–${range.max} professores`;
const professorColors = { 'nextfit:28143012':205, 'nextfit:38099183':325, 'nextfit:38099218':350, 'nextfit:38099701':140, 'nextfit:28143132':175 };
function professorColor(teacher) {
  const id = teacher.id;
  const hash = [...id].reduce((value, char) => (Math.imul(value, 31) + char.charCodeAt(0)) >>> 0, 0);
  const hue = professorColors[id] ?? ({rose:330,green:145,blue:205}[teacher.color_group || 'blue'] + hash % 15);
  return { '--teacher-hue': hue };
}
const clock = h => `${String(h).padStart(2,'0')}:00`;

export function SchedulePage() {
  const [teachers, setTeachers] = useState([]), [users, setUsers] = useState([]);
  const [chosen, setChosen] = useState(''), [name, setName] = useState(''), [selected, setSelected] = useState('');
  const [month, setMonth] = useState(currentMonth), [error, setError] = useState(''), [usersError, setUsersError] = useState('');
  const [loadFailed, setLoadFailed] = useState(false);
  const [salaryMigration, setSalaryMigration] = useState('');
  const revision = useRef(0);
  const [loading, setLoading] = useState(true), [saving, setSaving] = useState(false), [dirty, setDirty] = useState(false), [message, setMessage] = useState('');
  async function loadUsers() { try { const data = await api('/api/admin/schedule/users'); setUsers(data.users); setUsersError(''); } catch(e) { setUsersError(e.message); } }
  useEffect(() => { api('/api/admin/schedule').then(data => { const initialMonth=currentMonth(); setTeachers(data.teachers.map(t=>withMonthlySalary(t,initialMonth))); if(data.teachers.some(t=>t.salary==null && Number(t.rate)>0)) { setSalaryMigration(`Valores antigos por hora foram convertidos em salário mensal usando as horas de ${initialMonth.split('-').reverse().join('/')}. Confira os salários e clique em Salvar horários.`); setDirty(true); } }).catch(e => { setError(e.message); setLoadFailed(true); }).finally(() => setLoading(false)); loadUsers(); }, []);
  function change(next) { revision.current += 1; setTeachers(next); setDirty(true); setMessage(''); }
  function update(id, patch) { change(teachers.map(t => t.id === id ? {...t, ...patch} : t)); }
  function addNext() { const user = users.find(u => u.id === chosen); if (user && !teachers.some(t => t.id === `nextfit:${user.id}`)) change([...teachers, {id: `nextfit:${user.id}`, name: user.name, source:'nextfit', rate:0, salary:0, shifts:[]}]); setChosen(''); }
  function addTest(e) { e.preventDefault(); if (!name.trim()) return; change([...teachers, {id:`test:${crypto.randomUUID()}`, name:name.trim(), source:'test', rate:0, salary:0, shifts:[]}]); setName(''); }
  async function save() { if (teachers.some(t=>t.salary==='' || !Number.isFinite(Number(t.salary)) || Number(t.salary)<0 || Number(t.salary)>100000000)) { setError('Preencha um salário mensal válido para cada professor (zero é permitido).'); return; } if (teachers.some(t => !t.name.trim())) { setError('Preencha o nome de todos os professores antes de salvar.'); return; } const savedRevision = revision.current; setSaving(true); setError(''); try { const data = await api('/api/admin/schedule', {method:'PUT', body:JSON.stringify({teachers})}); if (revision.current === savedRevision) { setTeachers(data.teachers); setDirty(false); setMessage('Horários e salários salvos.'); setSalaryMigration(''); } else { setMessage('A versão anterior foi salva. Salve novamente as alterações recentes.'); } } catch(e) { setError(e.message); setMessage('Não foi possível salvar. Tente novamente.'); } finally { setSaving(false); } }
  const total = teachers.reduce((n,t) => n + Number(t.salary || 0), 0);
  const selectedTeacher = teachers.find(t => t.id === selected);
  function toggleSlot(day, hour) {
    if (!selectedTeacher) return;
    const start = hour * 60, end = start + 60;
    const matching = selectedTeacher.shifts.findIndex(s => s.day === day && minutes(s.start) === start && minutes(s.end) === end);
    if (matching >= 0) update(selected, {shifts: selectedTeacher.shifts.filter((_,i) => i !== matching)});
    else if (!selectedTeacher.shifts.some(s => overlaps(s,day,start,end))) update(selected, {shifts:[...selectedTeacher.shifts,{day,start:clock(hour),end:clock(hour+1)}]});
  }
  return <Shell className="schedule-page" title="Horários e salários" subtitle="Monte uma escala semanal e simule a remuneração da equipe.">
    <div className="schedule-layout">
    <ErrorBox error={error}/>
    {usersError && <div className="notice error">{usersError} <button className="button" onClick={loadUsers}>Tentar novamente</button></div>}
    {loading ? <p>Carregando horários…</p> : loadFailed ? <p>Não foi possível carregar a escala salva. Atualize a página para tentar novamente.</p> : <>
    <div className="schedule-setup">
      <section className="dw-section schedule-panel">
        <h2>Equipe da escala</h2>
        <p className="schedule-help">A lista do NEXT mostra usuários ativos. Confirme quais são professores ou inclua um nome de teste. A escala e os valores são visíveis somente para a administração.</p>
        <div className="schedule-add">
          <div className="schedule-add-group">
            <label>Adicionar usuário do NEXT
              <select value={chosen} onChange={e => setChosen(e.target.value)}>
                <option value="">Selecione um usuário</option>
                {users.filter(u => !teachers.some(t => t.id === `nextfit:${u.id}`)).map(u => <option value={u.id} key={u.id}>{u.name}</option>)}
              </select>
            </label>
            <button className="button" disabled={!chosen} onClick={addNext}>Adicionar</button>
          </div>
          <form className="schedule-add-group" onSubmit={addTest}>
            <label>Professor para teste
              <input value={name} maxLength={120} onChange={e => setName(e.target.value)} placeholder="Nome do professor" />
            </label>
            <button className="button" disabled={!name.trim()}>Incluir teste</button>
          </form>
        </div>
      </section>
      <section className="dw-section schedule-panel schedule-month">
        <div className="schedule-month-fields">
          <label>Mês da simulação<input type="month" value={month} onChange={e => setMonth(e.target.value)} /></label>
          <div className="schedule-month-total"><span>Total de salários mensais</span><strong>{money(total)}</strong></div>
        </div>
        <details className="schedule-calculation">
          <summary>Como o valor por hora é calculado</summary>
          <p className="schedule-help">Preencha o salário mensal total. Valor por hora = salário mensal ÷ horas previstas no mês selecionado, contando os dias reais do calendário. O salário informado permanece fixo. O valor por hora muda ao alterar o mês ou a escala. A mesma escala se repete em todos os sábados, e essas horas já estão incluídas no total. O cálculo desconsidera faltas, feriados, adicionais e encargos. Horários devem começar e terminar no mesmo dia.</p>
        </details>
      </section>
    </div>
    {salaryMigration && <p className="notice">{salaryMigration}</p>}
    {!teachers.length && <p>Adicione um professor para começar a montar a escala.</p>}
    <section className="dw-section schedule-board">
      <div className="schedule-board-header">
        <div>
          <h2>Quadro semanal da equipe</h2>
          <p className="schedule-help">Selecione um professor e clique nas células para editar horas inteiras. Para ajustar os minutos, use os detalhes abaixo da grade.</p>
        </div>
        <label className="schedule-picker">Professor para editar
          <select value={selected} onChange={e => setSelected(e.target.value)}>
            <option value="">Selecione um professor</option>
            {teachers.map(t => <option value={t.id} key={t.id}>{t.name}{t.source === 'test' ? ' (teste)' : ''}</option>)}
          </select>
        </label>
      </div>
      <div className="schedule-grid-wrap" role="region" aria-label="Grade de horários" tabIndex={0}><table className="schedule-grid"><thead><tr><th scope="col">Horário</th>{days.map(day => <th scope="col" key={day}>{day}</th>)}</tr></thead><tbody>
      {Array.from({length:17},(_,i) => i+5).map(hour => <tr key={hour}><th scope="row">{clock(hour)}–{clock(hour+1)}</th>{days.map((day,index) => { const start=hour*60, end=start+60; const totalCoverage=coverageRange(teachers,index,start,end,null); const testCoverage=coverageRange(teachers,index,start,end,'test'); const present=teachers.filter(t => t.shifts.some(s => overlaps(s,index,start,end))); const exact=selectedTeacher?.shifts.some(s => s.day===index && minutes(s.start)===start && minutes(s.end)===end); const partial=selectedTeacher?.shifts.some(s => overlaps(s,index,start,end)) && !exact; return <td key={day}><div className="schedule-cell"><strong className="schedule-coverage">{coverageLabel(totalCoverage)}</strong>{testCoverage.max > 0 && <small className="schedule-test-coverage">Inclui {coverageLabel(testCoverage)} de teste</small>}{present.map(t => <span className="schedule-person" style={professorColor(t)} key={t.id}>{t.name}{t.source === 'test' ? ' · teste' : ''}<small>{t.shifts.filter(s => overlaps(s,index,start,end)).map(s => ` ${s.start.slice(0,5)}–${s.end.slice(0,5)}`).join(',')}</small></span>)}<button type="button" className="schedule-cell-button" disabled={!selectedTeacher || partial} onClick={() => toggleSlot(index,hour)} aria-label={`${exact ? 'Remover' : 'Adicionar'} ${selectedTeacher?.name || 'professor'}: ${day} ${clock(hour)} às ${clock(hour+1)}`} title={partial ? 'Ajuste este horário nos detalhes do professor' : ''}>{exact ? '−' : '+'}</button></div></td>; })}</tr>)}
      </tbody></table></div><p className="schedule-help schedule-grid-note">A grade mostra intervalos das 5h às 22h. A contagem inclui os professores de teste previstos; a quantidade de testes incluída aparece indicada abaixo do total. Se a cobertura mudar dentro da hora, mostramos o mínimo e o máximo (ex.: 1–2). Qualquer horário salvo fora dessa faixa continua disponível nos detalhes do professor.</p></section>
    {teachers.map(t => { const weekly = t.shifts.reduce((n,s) => n + duration(s), 0), summary = monthSummary(t.shifts,month), monthly = summary.total, hourly = hourlyValue(t.salary,monthly); return <section className="dw-section schedule-card" key={t.id}>
      <div className="dw-section-head"><div><h2>{t.name}</h2>{t.source === 'test' && <div className="schedule-test-edit"><label>Nome do professor de teste<input maxLength={120} value={t.name} onChange={e => update(t.id,{name:e.target.value})}/></label><label>Cor<select value={t.color_group || 'blue'} onChange={e => update(t.id,{color_group:e.target.value})}><option value="rose">Rosa</option><option value="blue">Azul</option><option value="green">Verde</option></select></label></div>}<small>{t.source === 'test' ? 'Professor de teste' : 'Usuário do NEXT'}</small></div><button className="button" onClick={() => { if (window.confirm(`Remover ${t.name} desta escala?`)) change(teachers.filter(x => x.id !== t.id)); }}>Remover</button></div>
      <div className="schedule-card-body">
      <div className="schedule-summary"><label>Salário mensal total (R$)<input type="number" min="0" max="100000000" step="0.01" value={t.salary} onChange={e => update(t.id,{salary:e.target.value})}/></label><span>Por semana <strong>{hours(weekly)}</strong></span><span>No mês <strong>{hours(monthly)}</strong></span><span>Sábados no mês <strong>{summary.saturdays}</strong></span><span>Horas por sábado <strong>{hours(summary.perSaturday)}</strong></span><span>Horas de sábado no mês <strong>{hours(summary.saturdayMinutes)}</strong></span><span className="schedule-hourly">Valor por hora <strong>{hourly===null?'—':money(hourly)}</strong>{monthly===0 && <small>Cadastre horários para calcular</small>}</span></div>
      <ReplicateSchedule teacher={t} onApply={shifts=>update(t.id,{shifts})}/>
      <details className="schedule-details"><summary>Ver e editar horários de {t.name}</summary>
      {days.map((day, index) => <div className="schedule-day" key={day}><strong>{day}</strong><div>{t.shifts.map((shift,i) => shift.day === index && <div className="schedule-shift" key={i}><label>Início<input type="time" value={shift.start.slice(0,5)} onChange={e => update(t.id,{shifts:t.shifts.map((s,j) => i === j ? {...s,start:e.target.value} : s)})}/></label><label>Fim<input type="time" value={shift.end.slice(0,5)} onChange={e => update(t.id,{shifts:t.shifts.map((s,j) => i === j ? {...s,end:e.target.value} : s)})}/></label><button className="button" aria-label={`Remover horário de ${day}`} onClick={() => update(t.id,{shifts:t.shifts.filter((_,j) => i !== j)})}>×</button></div>)}</div><button className="button" onClick={() => update(t.id,{shifts:[...t.shifts,{day:index,start:'08:00',end:'12:00'}]})}>+ Horário</button></div>)}
      </details>
      </div>
    </section>; })}
    <div className={`schedule-save-bar${dirty || saving ? " is-pending" : ""}`}><span role="status">{message || (dirty ? 'Alterações não salvas' : 'Horários atualizados')}</span><button className="schedule-save-button" disabled={!dirty || saving} onClick={save}>{saving ? 'Salvando…' : 'Salvar horários'}</button></div></>}
    </div>
  </Shell>;
}
