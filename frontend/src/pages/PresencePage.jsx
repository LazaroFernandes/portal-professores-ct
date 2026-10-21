import "../styles/presence.css";
import { AdminNav } from "../components/AdminNav";
import { Check, ChevronDown, Dumbbell, LogOut, Users, X } from "lucide-react";
import { Fragment, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, query } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, Loading } from "../components/AsyncState";


const localTime = new Intl.DateTimeFormat("pt-BR", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "America/Sao_Paulo",
});

function currentWeekStart() {
  const day = new Date();
  day.setHours(12, 0, 0, 0);
  day.setDate(day.getDate() - ((day.getDay() + 6) % 7));
  return day.toISOString().slice(0, 10);
}

function detailValue(value) {
  return value === null || value === undefined || value === "" ? "—" : value;
}

function statusClass(status) {
  if (status === "ATENDIMENTO FINALIZADO") return "attendance-finished";
  if (status === "TREINO CONCLUÍDO") return "finished";
  return "active";
}

function TrainingDetails({ detail }) {
  return <div className="training-detail-panel">
    <div className="training-detail-heading">
      <div className="training-detail-icon"><Dumbbell size={20} /></div>
      <div><span>Treino do dia</span><h3>{detail.name}</h3></div>
    </div>
    <div className="training-detail-meta">
      <span><small>Sessão</small><strong>{detail.session} de {detail.total_sessions || 1}</strong></span>
      <span><small>Frequência</small><strong>{detail.weekly_frequency ? `${detail.weekly_frequency}x por semana` : "Não informada"}</strong></span>
      <span><small>Professor da ficha</small><strong>{detail.coach || "Não informado"}</strong></span>
    </div>
    {detail.notes && <p className="training-detail-note"><strong>Orientação:</strong> {detail.notes}</p>}
    <div className="training-exercise-list">
      <div className="training-exercise-header"><strong>Exercícios da sessão</strong><span>{detail.exercises.length}</span></div>
      {detail.exercises.length ? detail.exercises.map((exercise, index) => <div className="training-exercise-row" key={`${exercise.name}-${index}`}>
        <span className="training-exercise-order">{index + 1}</span>
        <div className="training-exercise-name"><strong>{exercise.name}</strong>{exercise.notes && <small>{exercise.notes}</small>}</div>
        <span><small>Séries</small><strong>{detailValue(exercise.sets)}</strong></span>
        <span><small>Repetições</small><strong>{detailValue(exercise.repetitions)}</strong></span>
        <span><small>Carga</small><strong>{detailValue(exercise.load)}</strong></span>
        <span><small>Intervalo</small><strong>{detailValue(exercise.rest)}</strong></span>
      </div>) : <p className="empty-inline">Nenhum exercício informado para esta sessão.</p>}
    </div>
  </div>;
}

export function AttendanceModal({ student, onClose, onSaved }) {
  const [form, setForm] = useState({
    desempenho: student.performance || "Bom",
    teve_dor: student.had_pain || false,
    descricao_dor: student.pain_description || "",
    observacao: student.observation || "",
    evolucao: student.evolution || "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  async function submit(event) {
    event.preventDefault(); setSaving(true); setError(null);
    try {
      await api(`/api/presence/${student.id}/attendance`, { method: "PUT", body: JSON.stringify(form) });
      await onSaved(); onClose();
    } catch (reason) { setError(reason); }
    finally { setSaving(false); }
  }

  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <form className="modal attendance-modal" onSubmit={submit}>
      <button className="modal-close" type="button" onClick={onClose} aria-label="Fechar"><X /></button>
      <span className="eyebrow">REGISTRO DIÁRIO</span><h2>Confirmar atendimento</h2>
      <p><strong>{student.name}</strong> · {student.professor || "Professor não definido"}</p>
      <label>Desempenho<select value={form.desempenho} onChange={(event) => setForm({ ...form, desempenho: event.target.value })}>
        {["Muito bom", "Bom", "Regular", "Ruim"].map((value) => <option key={value}>{value}</option>)}
      </select></label>
      <label>Dor ou desconforto<select value={form.teve_dor ? "sim" : "nao"} onChange={(event) => setForm({ ...form, teve_dor: event.target.value === "sim" })}>
        <option value="nao">Não</option><option value="sim">Sim</option>
      </select></label>
      {form.teve_dor && <label>Qual dor ou desconforto?<textarea required rows="3" value={form.descricao_dor} onChange={(event) => setForm({ ...form, descricao_dor: event.target.value })} /></label>}
      <label>Observação do treino<textarea rows="4" value={form.observacao} onChange={(event) => setForm({ ...form, observacao: event.target.value })} placeholder="Execução, ajustes, dificuldades e orientações..." /></label>
      <label>Evolução ou informação relevante<textarea rows="4" value={form.evolucao} onChange={(event) => setForm({ ...form, evolucao: event.target.value })} placeholder="Carga, técnica ou evolução observada..." /></label>
      {error && <div className="notice error">{error.message}</div>}
      <button className="button primary large" disabled={saving}>{saving ? "Salvando..." : "Confirmar atendimento"}</button>
    </form>
  </div>;
}

export function PresencePage() {
  const { session, logout } = useAuth();
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState(null);
  const [professor, setProfessor] = useState("Todos");
  const [expandedId, setExpandedId] = useState(null);
  const [trainingDetails, setTrainingDetails] = useState({});
  const [detailErrors, setDetailErrors] = useState({});
  const [loadingDetail, setLoadingDetail] = useState(null);
  const [attendanceStudent, setAttendanceStudent] = useState(null);
  const [weekly, setWeekly] = useState(null);
  const [weeklyError, setWeeklyError] = useState(null);

  async function load() {
    try { setPayload(await api("/api/presence")); setError(null); }
    catch (reason) { setError(reason); }
  }

  useEffect(() => {
    load(); const poll = window.setInterval(load, 15000);
    return () => window.clearInterval(poll);
  }, []);

  const students = useMemo(() => (payload?.students || []).filter((student) =>
    professor === "Todos" || (professor === "Professor não definido" ? !student.professor : student.professor === professor)
  ), [payload, professor]);
  const professorOptions = [...(payload?.professors || [])];
  if ((payload?.students || []).some((student) => !student.professor)) professorOptions.push("Professor não definido");

  const weeklyProfessor = session.role === "professor"
    ? session.name
    : professor !== "Todos" && professor !== "Professor não definido" ? professor : "";

  useEffect(() => {
    let active = true;
    if (!weeklyProfessor) { setWeekly(null); setWeeklyError(null); return undefined; }
    setWeekly(null); setWeeklyError(null);
    query("/api/professor/week", { start: currentWeekStart(), professor: weeklyProfessor })
      .then((data) => { if (active) setWeekly(data); })
      .catch((reason) => { if (active) setWeeklyError(reason); });
    return () => { active = false; };
  }, [weeklyProfessor]);

  async function toggleTraining(student) {
    if (expandedId === student.id) { setExpandedId(null); return; }
    setExpandedId(student.id);
    if (trainingDetails[student.id] || !student.training_id) return;
    setLoadingDetail(student.id); setDetailErrors((current) => ({ ...current, [student.id]: null }));
    try {
      const detail = await api(`/api/presence/${student.id}/training`);
      setTrainingDetails((current) => ({ ...current, [student.id]: detail }));
    }
    catch (reason) { setDetailErrors((current) => ({ ...current, [student.id]: reason })); }
    finally { setLoadingDetail(null); }
  }

  if (!payload && !error) return <div className="page presence-page"><Loading label="Buscando acessos de hoje..." /></div>;
  if (!payload && error) return <div className="page presence-page"><ErrorState error={error} retry={load} /></div>;

  return <div className="page presence-page">
    <AdminNav />
    <div className="page-heading"><div><span className="eyebrow">OPERAÇÃO DIÁRIA</span><h1>Alunos de hoje</h1><p>Acessos reais registrados no NextFit em {new Date().toLocaleDateString("pt-BR")}.</p></div><div className="presence-actions"><Link className="button ghost" to="/pendencias">Pendências anteriores</Link><button className="button ghost" onClick={logout}><LogOut size={17} /> Sair</button></div></div>
    <div className="notice presence-notice">Esta lista mostra acessos do dia. Não há confirmação automática de saída nem de presença física atual. Última atualização dos acessos: {payload.last_access_sync ? localTime.format(new Date(payload.last_access_sync)) : "ainda não sincronizado"}.</div>
    <div className="today-toolbar"><label>Professor<select value={professor} onChange={(event) => setProfessor(event.target.value)}><option>Todos</option>{professorOptions.map((name) => <option key={name}>{name}</option>)}</select></label><div><strong>{students.length}</strong><span>{students.length === 1 ? "aluno exibido" : "alunos exibidos"}</span></div></div>
    {error && <div className="notice error presence-notice">Erro ao atualizar acessos: {error.message}</div>}
    {payload.sync_error && <div className="notice presence-notice">Os últimos dados salvos continuam disponíveis. Falha na atualização: {payload.sync_error}</div>}
    {!students.length ? <section className="state-card presence-empty"><Users size={34} /><strong>Nenhum acesso encontrado para este filtro</strong><p>Novos acessos aparecem automaticamente em até {payload.poll_seconds} segundos.</p></section> : <div className="table-card presence-table"><div className="table-scroll"><table>
      <thead><tr><th>Aluno</th><th>Professor</th><th>Entrada</th><th>Sessão</th><th>Status</th><th>Ação</th></tr></thead>
      <tbody>{students.map((student) => {
        const expanded = expandedId === student.id;
        return <Fragment key={student.id}><tr>
          <td data-label="Aluno"><button className="student-name-button" onClick={() => toggleTraining(student)} aria-expanded={expanded}><strong>{student.name}</strong><ChevronDown className={expanded ? "rotated" : ""} size={17} /></button>{student.shift && <small className="table-subtext">{student.shift}</small>}</td>
          <td data-label="Professor">{student.professor || <span className="missing-value">Professor não definido</span>}</td>
          <td data-label="Entrada">{localTime.format(new Date(student.entered_at))}</td>
          <td data-label="Sessão">{student.training_session ? `Sessão ${student.training_session}` : <span className="missing-value">Sem ficha ativa</span>}</td>
          <td data-label="Status"><span className={`workout-status ${statusClass(student.status)}`}>{student.status}</span></td>
          <td data-label="Ação"><button className={`button small ${student.attendance_finalized_at ? "ghost" : "primary"}`} onClick={() => setAttendanceStudent(student)}><Check size={16} />{student.attendance_finalized_at ? "Editar registro" : "Confirmar"}</button></td>
        </tr>{expanded && <tr className="presence-detail-row"><td colSpan="6">
          <div className="student-context-grid"><span><small>Código</small><strong>{student.client_id}</strong></span><span><small>Ficha</small><strong>{student.training_name || "Sem ficha ativa"}</strong></span><span><small>Uso da ficha</small><strong>{student.training_usage_current ?? student.training_usage_baseline ?? "—"}</strong></span>{student.workout_finished_at && <span><small>Treino concluído</small><strong>{localTime.format(new Date(student.workout_finished_at))}</strong></span>}</div>
          {student.student_lookup_error && <div className="notice training-inline-notice">Erro ao localizar aluno: {student.student_lookup_error}</div>}
          {student.training_error && <div className="notice training-inline-notice">{student.training_error}</div>}
          {!student.training_id && <p className="empty-inline">O acesso foi mantido, mas nenhuma ficha ativa foi encontrada.</p>}
          {loadingDetail === student.id && <div className="training-detail-state"><span className="spinner" /> Carregando treino do dia...</div>}
          {detailErrors[student.id] && <div className="notice error training-detail-error">Erro ao consultar detalhes do treino: {detailErrors[student.id].message}</div>}
          {trainingDetails[student.id] && <TrainingDetails detail={trainingDetails[student.id]} />}
        </td></tr>}</Fragment>;
      })}</tbody>
    </table></div></div>}
    <section className="weekly-presence-section">
      <div className="weekly-presence-heading"><div><span className="eyebrow">ACOMPANHAMENTO</span><h2>Lista semanal</h2><p>Carteira completa e situação dos registros desta semana.</p></div>{weeklyProfessor && <Link className="button ghost" to="/registro">Abrir registro semanal</Link>}</div>
      {!weeklyProfessor ? <div className="state-card weekly-empty"><Users size={30} /><strong>Selecione um professor</strong><p>A lista semanal será exibida para a carteira escolhida acima.</p></div>
        : weeklyError ? <ErrorState error={weeklyError} />
        : !weekly ? <Loading label="Carregando lista semanal..." />
        : <>
          <div className="weekly-summary">
            <div><span>Professor</span><strong>{weekly.professor}</strong></div>
            <div><span>Semana</span><strong>{weekly.start} a {weekly.end}</strong></div>
            <div><span>Alunos</span><strong>{weekly.summary.total}</strong></div>
            <div><span>Preenchidos</span><strong className="weekly-completed">{weekly.summary.completed}</strong></div>
            <div><span>Pendentes</span><strong className={weekly.summary.pending ? "weekly-pending" : "weekly-completed"}>{weekly.summary.pending}</strong></div>
          </div>
          <div className="table-card presence-table weekly-table"><div className="table-scroll"><table>
            <thead><tr><th>Aluno</th><th>Turno / modalidade</th><th>Frequência</th><th>Desempenho</th><th>Situação</th></tr></thead>
            <tbody>{weekly.students.map((student) => <tr key={student.client_id}>
              <td data-label="Aluno"><strong>{student.name}</strong>{student.plan && <small className="table-subtext">{student.plan}</small>}</td>
              <td data-label="Turno / modalidade">{[student.shift, student.modality].filter(Boolean).join(" · ") || <span className="missing-value">Não informado</span>}</td>
              <td data-label="Frequência">{student.frequency || <span className="missing-value">Pendente</span>}</td>
              <td data-label="Desempenho">{student.performance || <span className="missing-value">Pendente</span>}</td>
              <td data-label="Situação"><span className={`weekly-status ${student.completed ? "complete" : "pending"}`}>{student.completed ? "PREENCHIDO" : "PENDENTE"}</span></td>
            </tr>)}</tbody>
          </table></div></div>
        </>}
    </section>
    {attendanceStudent && <AttendanceModal student={attendanceStudent} onClose={() => setAttendanceStudent(null)} onSaved={load} />}
  </div>;
}
