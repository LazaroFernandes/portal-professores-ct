import { Dumbbell, TrendingUp, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { Empty, ErrorState, Loading } from "../components/AsyncState";
import { DataTable } from "../components/DataTable";
import { Kpi, KpiGrid } from "../components/Kpi";

export function TrainingPage() {
  const [students, setStudents] = useState([]); const [selected, setSelected] = useState(""); const [data, setData] = useState(null); const [error, setError] = useState(null); const [history, setHistory] = useState(null);
  useEffect(() => { api("/api/admin/training/students").then((rows) => { setStudents(rows); if (rows.length) setSelected(String(rows[0].client_id)); }).catch(setError); }, []);
  useEffect(() => { if (selected) { setData(null); api(`/api/admin/training/students/${selected}`).then(setData).catch(setError); } }, [selected]);
  if (error) return <div className="page"><ErrorState error={error} /></div>;
  return <div className="page"><div className="page-heading"><div><span className="eyebrow">TREINAMENTO</span><h1>Evolução dos alunos</h1><p>Ficha atual, volume e histórico de carga por exercício.</p></div><div className="heading-icon"><Dumbbell /></div></div>
    <div className="filter-bar"><label>Aluno<select value={selected} onChange={(e) => setSelected(e.target.value)}>{students.map((student) => <option value={student.client_id} key={student.client_id}>{student.name}</option>)}</select></label></div>
    {!selected ? <Empty title="Nenhum treino sincronizado" /> : !data ? <Loading /> : <div className="training-grid"><section className="section-stack"><h2>Treino atual</h2>{data.sessions.map((session) => <div className="panel" key={session.name}><div className="section-title"><h3>Sessão {session.name}</h3><span className="badge">{session.exercises.length}</span></div><div className="exercise-list">{session.exercises.map((exercise, index) => { const key = `${session.name}::${exercise.Exercicio || ""}`; const values = data.histories[key] || []; return <article className="exercise" key={`${exercise.Exercicio}-${index}`}><div><strong>{exercise.Exercicio}</strong><span>{[exercise.GrupoMuscular, exercise.Carga && `Carga ${exercise.Carga}`, exercise.Repeticoes && `Reps ${exercise.Repeticoes}`, exercise.Intervalo].filter(Boolean).join(" · ")}</span></div><button className="button ghost" onClick={() => setHistory({ name: exercise.Exercicio, session: session.name, values })}><TrendingUp size={16} /> Evolução</button></article>; })}</div></div>)}</section><aside className="section-stack"><KpiGrid><Kpi label="Volume total" value={`${data.total_sets} séries`} /></KpiGrid><div className="panel"><h2>Volume por grupo muscular</h2><DataTable rows={data.volume} columns={[{ key: "group", label: "Grupo" }, { key: "exercises", label: "Exercícios" }, { key: "sets", label: "Séries" }]} filename="volume-muscular" searchable={false} /></div></aside></div>}
    {history && <HistoryModal history={history} close={() => setHistory(null)} />}
  </div>;
}

function HistoryModal({ history, close }) {
  const chartData = history.values.filter((row) => row.CargaNum != null).map((row) => ({ date: row.DataExecucao, load: row.CargaNum }));
  const summary = useMemo(() => chartData.length ? { last: chartData.at(-1).load, record: Math.max(...chartData.map((row) => row.load)), delta: chartData.at(-1).load - chartData[0].load } : null, [chartData]);
  return <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && close()}><section className="modal modal-wide"><button className="modal-close" onClick={close}><X /></button><h2>{history.name}</h2><p>Sessão {history.session} · {history.values.length} execuções</p>{summary ? <><KpiGrid><Kpi label="Última carga" value={`${summary.last} kg`} /><Kpi label="Recorde" value={`${summary.record} kg`} tone="good" /><Kpi label="Variação" value={`${summary.delta >= 0 ? "+" : ""}${summary.delta} kg`} tone={summary.delta >= 0 ? "good" : "warning"} /></KpiGrid><div className="chart"><ResponsiveContainer width="100%" height={300}><LineChart data={chartData}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" hide /><YAxis domain={["dataMin - 2", "dataMax + 2"]} /><Tooltip /><Line type="monotone" dataKey="load" stroke="#f59e0b" strokeWidth={3} dot={{ r: 4 }} /></LineChart></ResponsiveContainer></div></> : <Empty title="Sem cargas numéricas" text="O histórico textual continua disponível abaixo." />}<DataTable rows={history.values} filename={`evolucao-${history.name}`} /></section></div>;
}
