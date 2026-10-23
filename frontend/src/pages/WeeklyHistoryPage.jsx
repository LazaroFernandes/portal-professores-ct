import { useState } from 'react';
import { Link } from 'react-router-dom';
import { currentWeek, shiftWeek, weekStart } from './professorAnalysisUtils';
import { summarizeWeek, weekEnd } from './weeklyHistoryUtils';
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
  const summary = summarizeWeek(data?.students || [], { professor, search, situation });
  return <Shell title="Histórico semanal" subtitle="A semana reunida a partir dos registros diários. O professor registra uma vez; a gerência acompanha a continuidade.">
    <div className="dw-toolbar">
      <button className="button" onClick={() => setStart(shiftWeek(start, -1))}>← Semana anterior</button>
      <label>Semana de referência<input type="date" value={start} max={today()} onChange={e => { const value = weekStart(e.target.value); if (value) setStart(value); }}/></label>
      <button className="button" disabled={start >= currentWeek()} onClick={() => setStart(shiftWeek(start, 1))}>Próxima semana →</button>
      <button className="button" onClick={() => setStart(currentWeek())}>Semana atual</button>
      <button className="button" onClick={reload}>Atualizar</button>
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
