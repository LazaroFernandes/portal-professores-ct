import { Check, ChevronDown, ChevronLeft, ChevronRight, LogOut, Save, UserRound } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { query, api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Empty, ErrorState, Loading } from "../components/AsyncState";
import { Kpi, KpiGrid } from "../components/Kpi";

const performances = ["", "Muito bom", "Bom", "Regular", "Não está vindo", "Férias"];
const shifts = ["", "MANHÃ", "TARDE", "NOITE"];

function isoWeek(offset = 0) {
  const day = new Date();
  day.setHours(12, 0, 0, 0);
  day.setDate(day.getDate() - ((day.getDay() + 6) % 7) + offset * 7);
  return day.toISOString().slice(0, 10);
}

function shiftWeek(value, amount) {
  const day = new Date(`${value}T12:00:00`); day.setDate(day.getDate() + amount * 7); return day.toISOString().slice(0, 10);
}

function StudentCard({ student, start, professor, onSaved }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ frequencia: student.frequency, desempenho: student.performance, relato: student.report, turno: student.shift });
  const [status, setStatus] = useState("");
  const changed = form.frequencia !== student.frequency || form.desempenho !== student.performance || form.relato !== student.report || form.turno !== student.shift;
  async function save() {
    setStatus("saving");
    try {
      await api(`/api/professor/week/${start}/students/${student.client_id}${professor ? `?professor=${encodeURIComponent(professor)}` : ""}`, { method: "PUT", body: JSON.stringify(form) });
      setStatus("saved"); onSaved(); setTimeout(() => setStatus(""), 1800);
    } catch (error) { setStatus(error.message); }
  }
  return <article className={`student-card ${student.completed ? "complete" : ""}`}>
    <button className="student-summary" onClick={() => setOpen(!open)} aria-expanded={open}>
      <span className="completion">{student.completed ? <Check size={16} /> : null}</span><span><strong>{student.name}</strong><small>{[student.shift, student.modality, student.frequency && `Freq. ${student.frequency}`].filter(Boolean).join(" · ") || "Pendente"}</small></span><ChevronDown className={open ? "rotated" : ""} />
    </button>
    {open && <div className="student-form">
      {(student.plan || student.modality) && <p className="muted">Plano: {student.plan || "—"} {student.modality && `· ${student.modality}`}</p>}
      <div className="form-grid"><label>Turno<select value={form.turno} onChange={(e) => setForm({ ...form, turno: e.target.value })}>{shifts.map((value) => <option key={value} value={value}>{value || "Não informado"}</option>)}</select></label>
      <label>Frequência<input value={form.frequencia} onChange={(e) => setForm({ ...form, frequencia: e.target.value })} placeholder="Ex.: 3, férias…" /></label>
      <label>Desempenho<select value={form.desempenho} onChange={(e) => setForm({ ...form, desempenho: e.target.value })}>{performances.map((value) => <option key={value} value={value}>{value || "Selecione"}</option>)}</select></label></div>
      <label>Relato<textarea rows="4" value={form.relato} onChange={(e) => setForm({ ...form, relato: e.target.value })} placeholder="Treino, dificuldades, dores e evolução…" /></label>
      {status && status !== "saving" && status !== "saved" && <div className="notice error">{status}</div>}
      <button className="button primary" disabled={!changed || status === "saving"} onClick={save}><Save size={17} />{status === "saving" ? "Salvando…" : status === "saved" ? "Salvo" : "Salvar registro"}</button>
    </div>}
  </article>;
}

export function ProfessorPage() {
  const { session, logout } = useAuth();
  const [start, setStart] = useState(isoWeek());
  const [professor, setProfessor] = useState("");
  const [filter, setFilter] = useState("all");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(() => {
    setLoading(true); setError(null);
    query("/api/professor/week", { start, professor })
      .then((payload) => { setData(payload); if (!professor) setProfessor(payload.professor); })
      .catch(setError).finally(() => setLoading(false));
  }, [start, professor]);
  useEffect(load, [load]);
  const students = useMemo(() => (data?.students || []).filter((item) => filter === "all" || (filter === "completed" ? item.completed : !item.completed)), [data, filter]);
  async function openWeek() { await api(`/api/professor/week/open?start=${start}&professor=${encodeURIComponent(professor)}`, { method: "POST" }); load(); }

  if (loading && !data) return <Page><Loading label="Carregando seus alunos…" /></Page>;
  if (error && !data) return <Page><ErrorState error={error} retry={load} /></Page>;
  return <Page>
    <div className="page-heading"><div><span className="eyebrow">ACOMPANHAMENTO</span><h1>Registro semanal</h1><p>Atualize frequência, desempenho e observações da carteira.</p></div><div className="heading-actions"><div className="heading-icon"><UserRound /></div><button className="button logout-button" onClick={logout}><LogOut size={17} />Sair</button></div></div>
    {session.role === "admin" && <label className="inline-select">Professor<select value={professor} onChange={(event) => setProfessor(event.target.value)}>{data?.professors.map((name) => <option key={name}>{name}</option>)}</select></label>}
    <div className="week-picker"><button onClick={() => setStart(shiftWeek(start, -1))}><ChevronLeft /></button><div><strong>{data?.label}</strong><span>{data?.start} a {data?.end}</span></div><button onClick={() => setStart(shiftWeek(start, 1))}><ChevronRight /></button></div>
    {!data?.opened ? <div className="action-card"><strong>Esta semana ainda não foi aberta</strong><p>Crie os registros dos alunos ativos para começar o preenchimento.</p><button className="button primary" onClick={openWeek}>Abrir esta semana</button></div> : <>
      <KpiGrid><Kpi label="Alunos" value={data.summary.total} /><Kpi label="Preenchidos" value={data.summary.completed} tone="good" /><Kpi label="Pendentes" value={data.summary.pending} tone={data.summary.pending ? "warning" : "good"} /></KpiGrid>
      <div className="segmented">{[["all", "Todos"], ["pending", "Pendentes"], ["completed", "Preenchidos"]].map(([value, label]) => <button className={filter === value ? "active" : ""} onClick={() => setFilter(value)} key={value}>{label}</button>)}</div>
      <div className="student-list">{students.length ? students.map((student) => <StudentCard key={student.client_id} student={student} start={start} professor={professor} onSaved={load} />) : <Empty />}</div>
    </>}
  </Page>;
}

function Page({ children }) { return <div className="page narrow">{children}</div>; }
