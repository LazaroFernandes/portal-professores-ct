import { useState } from 'react';
import { Link } from 'react-router-dom';
import { currentWeek, shiftWeek, weekStart } from './professorAnalysisUtils';
import { summarizeWeek, weekEnd, attentionReasons, weeklyActions } from './weeklyHistoryUtils';
import { useData, Shell, ErrorBox, Badge, RecordText, History, today } from './DailyWorkflow';

const displayDate = value => value.split('-').reverse().join('/');

export function WeeklyHistoryPage() {
  const [start, setStart] = useState(currentWeek);
  const [professor, setProfessor] = useState('');
  const [search, setSearch] = useState('');
  const [situation, setSituation] = useState('');
  const [history, setHistory] = useState(null);
  const end = weekEnd(start);
  const { data, loading, error, reload } = useData('/api/daily/analysis', { start, end });
  const actionData = useData('/api/daily/actions');
  const summary = summarizeWeek(data?.students || [], { professor, search, situation });
  const activity = weeklyActions(actionData.data?.actions || [], { start, end, professor, search, clientIds: summary.students.map(s => s.client_id) });
  return <Shell title="Histórico semanal" subtitle="A semana reunida a partir dos registros diários. O professor registra uma vez; a gerência acompanha a continuidade.">
    <div className="dw-toolbar">
      <button className="button" onClick={() => setStart(shiftWeek(start, -1))}>← Semana anterior</button>
      <label>Semana de referência<input type="date" value={start} max={today()} onChange={e => { const value = weekStart(e.target.value); if (value) setStart(value); }}/></label>
      <button className="button" disabled={start >= currentWeek()} onClick={() => setStart(shiftWeek(start, 1))}>Próxima semana →</button>
      <button className="button" onClick={() => setStart(currentWeek())}>Semana atual</button>
      <button className="button" onClick={() => { reload(); actionData.reload(); }}>Atualizar</button>
    </div>
    <p><strong>{displayDate(start)} a {displayDate(end)}</strong>{start === currentWeek() && ' · Semana em andamento'}</p>
    <p className="dw-source">Consolidação automática dos acessos e registros diários disponíveis, de segunda a domingo. Cada aluno aparece uma vez, com seus dias detalhados. Edições no diário atualizam esta visão ao carregar ou atualizar a página.</p>
    <div className="dw-toolbar">
      <label className="dw-grow">Buscar aluno<input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Nome do aluno"/></label>
      <label>Professor<select value={professor} onChange={e => setProfessor(e.target.value)}><option value="">Todos</option>{data?.professors.map(name => <option key={name}>{name}</option>)}<option value="__unassigned">Sem responsável</option></select></label>
      <label>Alunos com<select value={situation} onChange={e => setSituation(e.target.value)}><option value="">Todas as situações</option><option value="pending">Dias sem registro</option><option value="attention">Ocorrências ou retornos</option></select></label>
    </div>
    <ErrorBox error={error}/>
    {data?.sync_error && <div className="notice error">A atualização do NEXT falhou. Os dados disponíveis podem estar desatualizados.</div>}
    {loading ? <p role="status">Consolidando os registros diários da semana…</p> : data && <>
      <div className="dw-stats">{[[summary.unique_students, 'Alunos nos filtros'], [summary.total, 'Acessos (aluno/dia)'], [summary.registered, 'Registros feitos'], [summary.pending, 'Dias sem registro']].map(([value,label]) => <div key={label}><strong>{value}</strong><span>{label}</span></div>)}</div>
      <p className="dw-source">{summary.not_observed} registro(s) de “não observado”, contabilizados separadamente. Os totais correspondem aos filtros acima. Acesso registrado não confirma permanência física na academia.</p>
      <section className="dw-section">
        <div className="dw-section-head"><h2>Ações e retornos da semana</h2><Link to="/acoes">Acompanhar ações →</Link></div>
        <p className="dw-source">Ações abertas ou atualizadas nesta semana, inclusive para alunos sem acesso no período, e acompanhamentos ainda abertos dos alunos deste recorte. O selo mostra a situação atual; a linha do tempo mostra quem fez cada atualização na semana. Os filtros de nome e professor se aplicam aqui; o filtro de situação dos registros se aplica somente aos registros diários.</p>
        <ErrorBox error={actionData.error}/>
        {actionData.loading ? <p role="status">Carregando acompanhamentos…</p> : actionData.data && <>
          {!activity.length && <p>Nenhuma ação na semana ou acompanhamento aberto dos alunos deste recorte.</p>}
          {activity.map(a => <article className="dw-week-student" key={a.id}>
            <div className="dw-section-head"><strong>{a.student_name}</strong><Badge status={a.status}/></div>
            <p>{a.title}</p><small>Responsável atual: {a.assigned_to} · Prazo: {a.due_date ? displayDate(a.due_date) : 'Não definido'}{a.overdue ? ' · Em atraso hoje' : ''}</small>
            {a.instruction && <p><b>Orientação atual:</b> {a.instruction}</p>}
            {a.result && <p><b>Último andamento / resultado:</b> {a.result}</p>}
            {a.weeklyEvents.map((event, i) => <div className="dw-history" key={i}>
              <strong>{event.actor} · {event.actor_role === 'admin' ? 'Gerência' : 'Professor'}</strong><small>{new Date(event.created_at).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' })}</small>
              <p>{event.payload.event === 'created' ? 'Abriu o acompanhamento' : event.payload.event === 'reopened' ? 'Reabriu o acompanhamento' : 'Atualizou o acompanhamento'} {event.payload.after?.status && <Badge status={event.payload.after.status}/>}</p>
              {event.payload.after?.result && <p><b>Andamento registrado:</b> {event.payload.after.result}</p>}
            </div>)}
          </article>)}
        </>}
      </section>
      <section className="dw-section">
        <h2>O que precisa da atenção do gerente</h2>
        <p className="dw-source">Ocorrências da semana e pendências de preenchimento nos filtros selecionados. Uma ocorrência é um relato, não uma confirmação de problema ainda aberto.</p>
        {summary.students.filter(s => s.attention || s.pending).sort((a,b) => b.attention - a.attention).map(student => <details className="dw-week-student" key={student.client_id}>
          <summary><strong>{student.student_name}</strong> · {student.attention} ocorrência(s) · {student.pending} dia(s) sem registro</summary>
          {student.pending > 0 && <p><b>{student.pending} dia(s) sem registro:</b> {student.records.filter(r => r.status === 'pending').map(r => `${displayDate(r.entered_at.slice(0,10))} · ${r.professor || 'Sem responsável'}`).join('; ')}</p>}
          {student.records.filter(r => attentionReasons(r).length).map(r => <div className="dw-history" key={r.id}><strong>{displayDate(r.entered_at.slice(0,10))} · {attentionReasons(r).join(' · ')}</strong><small>{r.actor || r.finalized_by || r.professor || 'Sem responsável'}</small><RecordText row={r}/></div>)}
          {actionData.data && <p>{actionData.data.actions.filter(a => a.client_id === student.client_id && a.status !== 'resolved').length} acompanhamento(s) atualmente aberto(s) para este aluno. <Link to="/acoes">Ver responsáveis e prazos →</Link></p>}
          <button className="button" onClick={() => setHistory(student)}>Ver histórico e resultados</button>
        </details>)}
        {!summary.students.some(s => s.attention || s.pending) && <p>Nenhuma ocorrência ou registro pendente neste recorte.</p>}
      </section>
      <section className="dw-section"><div className="dw-section-head"><h2>Resumo por professor</h2><Link to="/acoes">Ações e retornos →</Link></div>
        <div className="dw-team">{summary.teams.map(team => <article key={team.name}><strong>{team.name}</strong><p>{team.registered} registrados · {team.not_observed} não observados · <b>{team.pending} sem registro</b></p><small>{team.total} acessos (aluno/dia)</small></article>)}</div>
        {!summary.teams.length && <div className="dw-empty">Nenhum acesso diário disponível para esta semana e estes filtros.</div>}
      </section>
      <section className="dw-section"><div className="dw-section-head"><h2>A semana de cada aluno <small>{summary.unique_students}</small></h2></div>
        {summary.students.map(student => <article key={student.client_id} className="dw-week-student">
          <div className="dw-section-head"><div><strong>{student.student_name}</strong><small>{student.records.length} dia(s) com acesso · {student.registered} registrado(s) · {student.not_observed} não observado(s) · {student.pending} sem registro</small></div><button className="button" onClick={() => setHistory(student)}>Histórico completo</button></div>
          <details><summary>Ver os {student.records.length} dias desta semana</summary>
            {student.records.map(row => <div className="dw-history" key={row.id}><strong>{displayDate(row.entered_at.slice(0,10))}</strong> <Badge status={row.status}/><small>Responsável: {row.professor || 'Sem responsável'}{(row.actor || row.finalized_by) && ` · Registro por ${row.actor || row.finalized_by}`}</small><RecordText row={row}/>{row.open_actions?.length > 0 && <p><Link to="/acoes">{row.open_actions.length} ação(ões) atualmente em aberto para este aluno</Link></p>}</div>)}
          </details>
        </article>)}
        {!summary.students.length && <div className="dw-empty">Não há registros diários disponíveis neste recorte. Para o formulário usado antes da operação diária, consulte o arquivo antigo abaixo.</div>}
      </section>
    </>}
    <p className="dw-source">Os registros semanais anteriores foram preservados. <Link to="/admin/registros-semanais-antigos">Consultar arquivo semanal antigo →</Link></p>
    {history && <History row={history} onClose={() => setHistory(null)}/>}
  </Shell>;
}
