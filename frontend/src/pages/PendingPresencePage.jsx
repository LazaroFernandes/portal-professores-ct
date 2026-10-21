import { AdminNav } from "../components/AdminNav";
import { ArrowLeft, CalendarClock, Check, LogOut, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, Loading } from "../components/AsyncState";
import { AttendanceModal } from "./PresencePage";

const entryDate = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
  timeZone: "America/Sao_Paulo",
});

function pendingDays(enteredAt) {
  const entered = new Date(enteredAt);
  const today = new Date();
  entered.setHours(0, 0, 0, 0);
  today.setHours(0, 0, 0, 0);
  return Math.max(1, Math.round((today - entered) / 86400000));
}

export function PendingPresencePage() {
  const { session, logout } = useAuth();
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState(null);
  const [professor, setProfessor] = useState("Todos");
  const [selected, setSelected] = useState(null);

  async function load() {
    try { setPayload(await api("/api/presence/pending")); setError(null); }
    catch (reason) { setError(reason); }
  }

  useEffect(() => { load(); }, []);

  const students = useMemo(() => (payload?.students || []).filter((student) =>
    professor === "Todos" || (professor === "Professor não definido" ? !student.professor : student.professor === professor)
  ), [payload, professor]);
  const professorOptions = [...(payload?.professors || [])];
  if ((payload?.students || []).some((student) => !student.professor)) professorOptions.push("Professor não definido");

  if (!payload && !error) return <div className="page presence-page"><Loading label="Buscando pendências anteriores..." /></div>;
  if (!payload && error) return <div className="page presence-page"><ErrorState error={error} retry={load} /></div>;

  return <div className="page presence-page">
    <AdminNav />
    <div className="page-heading"><div><span className="eyebrow">ACOMPANHAMENTO DIÁRIO</span><h1>Pendências anteriores</h1><p>Atendimentos de dias passados que ainda precisam ser finalizados.</p></div><div className="presence-actions"><Link className="button ghost" to="/academia"><ArrowLeft size={17} />Alunos de hoje</Link><button className="button ghost" onClick={logout}><LogOut size={17} />Sair</button></div></div>
    <div className="pending-summary">
      <div className="pending-summary-icon"><CalendarClock /></div>
      <div><span>Total acumulado</span><strong>{students.length}</strong><p>{students.length === 1 ? "atendimento aguardando conclusão" : "atendimentos aguardando conclusão"}</p></div>
    </div>
    {session.role === "admin" && <div className="today-toolbar pending-toolbar"><label>Professor<select value={professor} onChange={(event) => setProfessor(event.target.value)}><option>Todos</option>{professorOptions.map((name) => <option key={name}>{name}</option>)}</select></label></div>}
    {error && <div className="notice error presence-notice">Erro ao atualizar pendências: {error.message}</div>}
    {!students.length ? <section className="state-card presence-empty"><Users size={34} /><strong>Nenhuma pendência anterior</strong><p>Todos os atendimentos dos dias anteriores foram finalizados.</p></section> : <div className="table-card presence-table pending-table"><div className="table-scroll"><table>
      <thead><tr><th>Aluno</th><th>Professor</th><th>Entrada</th><th>Em atraso</th><th>Treino</th><th>Ação</th></tr></thead>
      <tbody>{students.map((student) => <tr key={student.id}>
        <td data-label="Aluno"><strong>{student.name}</strong>{student.shift && <small className="table-subtext">{student.shift}</small>}</td>
        <td data-label="Professor">{student.professor || <span className="missing-value">Professor não definido</span>}</td>
        <td data-label="Entrada">{entryDate.format(new Date(student.entered_at))}</td>
        <td data-label="Em atraso"><span className="pending-age">{pendingDays(student.entered_at)} {pendingDays(student.entered_at) === 1 ? "dia" : "dias"}</span></td>
        <td data-label="Treino">{student.training_name || <span className="missing-value">Sem ficha ativa</span>}</td>
        <td data-label="Ação"><button className="button small primary" onClick={() => setSelected(student)}><Check size={16} />Finalizar</button></td>
      </tr>)}</tbody>
    </table></div></div>}
    {selected && <AttendanceModal student={selected} onClose={() => setSelected(null)} onSaved={load} />}
  </div>;
}
