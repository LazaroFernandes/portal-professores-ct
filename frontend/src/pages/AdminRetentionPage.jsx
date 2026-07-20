import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { query } from "../api/client";
import { Empty, ErrorState, Loading } from "../components/AsyncState";
import { DataTable } from "../components/DataTable";
import { Kpi, KpiGrid } from "../components/Kpi";

const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const percent = (value) => `${Math.round(Number(value || 0) * 100)}%`;

function defaultMonths() {
  const current = new Date();
  const previous = new Date(current.getFullYear(), current.getMonth() - 1, 1);
  return [previous.toISOString().slice(0, 7), current.toISOString().slice(0, 7)];
}

export function AdminRetentionPage() {
  const [[monthA, monthB], setMonths] = useState(defaultMonths);
  const [target, setTarget] = useState(8);
  const [group, setGroup] = useState("categoria");
  const [data, setData] = useState(null);
  const [modalities, setModalities] = useState(null);
  const [error, setError] = useState(null);
  const [section, setSection] = useState("retention");

  useEffect(() => {
    const [yearA, valueA] = monthA.split("-"); const [yearB, valueB] = monthB.split("-");
    setError(null);
    Promise.all([
      query("/api/admin/retention", { year_a: yearA, month_a: valueA, year_b: yearB, month_b: valueB, target }),
      query("/api/admin/retention/modalities", { year_a: yearA, month_a: valueA, year_b: yearB, month_b: valueB, group }),
    ]).then(([retention, modality]) => { setData(retention); setModalities(modality); }).catch(setError);
  }, [monthA, monthB, target, group]);

  return <div className="page">
    <div className="page-heading"><div><span className="eyebrow">GESTÃO</span><h1>Retenção e acompanhamento</h1><p>Status, engajamento e qualidade da carteira por professor.</p></div></div>
    <div className="filter-bar"><label>De<input type="month" value={monthA} onChange={(e) => setMonths([e.target.value, monthB])} /></label><label>Para<input type="month" value={monthB} onChange={(e) => setMonths([monthA, e.target.value])} /></label><label>Meta de presenças<input type="number" min="1" max="31" value={target} onChange={(e) => setTarget(e.target.value)} /></label></div>
    <div className="subnav">{[["retention", "Retenção"], ["modalities", "Modalidades"], ["attendance", "Presenças"], ["decline", "Queda de frequência"], ["comparison", "Digitada × real"], ["history", "Histórico do aluno"]].map(([value, label]) => <button key={value} className={section === value ? "active" : ""} onClick={() => setSection(value)}>{label}</button>)}</div>
    {error ? <ErrorState error={error} /> : !data ? <Loading /> : <>
      {section === "retention" && <Retention data={data} />}
      {section === "modalities" && <Modalities data={modalities} group={group} setGroup={setGroup} />}
      {section === "attendance" && <Attendance />}
      {section === "decline" && <Decline />}
      {section === "comparison" && <Comparison />}
      {section === "history" && <History />}
    </>}
  </div>;
}

function Retention({ data }) {
  const chart = data.professors.map((row) => ({ name: row.professor, status: Math.round(row.taxa_status * 100), engagement: Math.round(row.taxa_engajamento * 100) }));
  return <section className="section-stack"><KpiGrid><Kpi label={`Ativos em ${data.label_m1}`} value={data.total_ativos_m1} /><Kpi label="Retidos por status" value={percent(data.taxa_status_total)} tone="good" /><Kpi label="Retidos engajados" value={percent(data.taxa_engaj_total)} tone="good" /><Kpi label="Receita preservada" value={money.format(data.receita_preservada)} /><Kpi label="Alunos perdidos" value={data.alunos_perdidos} tone={data.alunos_perdidos ? "danger" : "good"} /></KpiGrid>
    <div className="panel"><h2>Retenção por professor</h2><div className="chart"><ResponsiveContainer width="100%" height={Math.max(260, chart.length * 52)}><BarChart data={chart} layout="vertical"><CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" domain={[0, 100]} unit="%" /><YAxis type="category" dataKey="name" width={145} tick={{ fontSize: 12 }} /><Tooltip /><Bar dataKey="status" name="Status" fill="#111827" radius={[0, 6, 6, 0]} /><Bar dataKey="engagement" name="Engajamento" fill="#f59e0b" radius={[0, 6, 6, 0]} /></BarChart></ResponsiveContainer></div></div>
    <div className="accordion-list">{data.professors.map((row) => <details key={row.professor} className="panel"><summary><span><strong>{row.professor}</strong><small>{row.ativos_m1} alunos · qualidade {percent(row.qualidade_registro)}</small></span><b>{percent(row.taxa_status)}</b></summary><div className="detail-grid"><div><h3>Perdidos ({row.perdidos.length})</h3><DataTable rows={row.perdidos} filename={`perdidos-${row.professor}`} /></div><div><h3>Em risco ({row.em_risco.length})</h3><DataTable rows={row.em_risco} filename={`risco-${row.professor}`} /></div><div><h3>Treino no período</h3><KpiGrid><Kpi label="Treinaram" value={row.training.alunos_com_execucao} /><Kpi label="Sessões" value={row.training.sessoes_finalizadas} /><Kpi label="Progressões" value={row.training.exercicios_progrediram} tone="good" /></KpiGrid><DataTable rows={row.training.top_alunos} filename={`treinos-${row.professor}`} /></div></div></details>)}</div>
  </section>;
}

function Modalities({ data, group, setGroup }) {
  if (!data) return <Loading />;
  return <section className="section-stack"><div className="filter-bar"><label>Agrupar por<select value={group} onChange={(e) => setGroup(e.target.value)}><option value="categoria">Categoria</option><option value="plano">Plano detalhado</option></select></label></div><KpiGrid><Kpi label="Ativos" value={data.total_ativos_m1} /><Kpi label="Retidos" value={percent(data.taxa_status_total)} tone="good" /><Kpi label="Receita preservada" value={money.format(data.receita_preservada)} /><Kpi label="Receita perdida" value={money.format(data.receita_perdida)} tone="danger" /></KpiGrid><DataTable rows={data.linhas} columns={[{ key: "modalidade", label: "Modalidade" }, { key: "ativos_m1", label: "Ativos" }, { key: "retidos_status", label: "Retidos" }, { key: "taxa_status", label: "Taxa", render: percent }, { key: "receita_preservada", label: "Receita preservada", render: money.format }]} filename="retencao-modalidades" /></section>;
}

function Attendance() {
  const [days, setDays] = useState(14); const [mode, setMode] = useState("missing"); const [rows, setRows] = useState(null); const [error, setError] = useState(null);
  useEffect(() => { setRows(null); query("/api/admin/attendance", { days, mode }).then(setRows).catch(setError); }, [days, mode]);
  return <section><div className="filter-bar"><label>Visão<select value={mode} onChange={(e) => setMode(e.target.value)}><option value="missing">Sumidos há mais de</option><option value="until">Faltando até</option><option value="recent">Vieram nos últimos</option></select></label><label>Dias<input type="number" min="1" max="60" value={days} onChange={(e) => setDays(e.target.value)} /></label></div>{error ? <ErrorState error={error} /> : rows ? <DataTable rows={rows} filename="acompanhamento-presenca" /> : <Loading />}</section>;
}

function Decline() {
  const [weeks, setWeeks] = useState(4); const [rows, setRows] = useState(null);
  useEffect(() => { setRows(null); query("/api/admin/attendance/decline", { weeks }).then(setRows); }, [weeks]);
  return <section><div className="filter-bar"><label>Semanas por janela<input type="number" min="2" max="8" value={weeks} onChange={(e) => setWeeks(e.target.value)} /></label></div>{rows ? <DataTable rows={rows} filename="queda-frequencia" /> : <Loading />}</section>;
}

function Comparison() {
  const [start, setStart] = useState(() => { const d = new Date(); d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); return d.toISOString().slice(0, 10); }); const [rows, setRows] = useState(null);
  useEffect(() => { setRows(null); query("/api/admin/weekly-comparison", { start }).then(setRows); }, [start]);
  return <section><div className="filter-bar"><label>Início da semana<input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label></div>{rows ? <DataTable rows={rows} filename="digitada-real" /> : <Loading />}</section>;
}

function History() {
  const [students, setStudents] = useState([]); const [selected, setSelected] = useState(""); const [data, setData] = useState(null);
  useEffect(() => { query("/api/admin/students").then((rows) => { setStudents(rows); if (rows.length) setSelected(String(rows[0].client_id)); }); }, []);
  useEffect(() => { if (selected) { setData(null); query(`/api/admin/students/${selected}/history`).then(setData); } }, [selected]);
  return <section><div className="filter-bar"><label>Aluno<select value={selected} onChange={(e) => setSelected(e.target.value)}>{students.map((item) => <option key={item.client_id} value={item.client_id}>{item.name}</option>)}</select></label></div>{data ? <><KpiGrid><Kpi label="Professor" value={data.Aluno?.Professor || "—"} /><Kpi label="Turno" value={data.Aluno?.Turno || "—"} /></KpiGrid><DataTable rows={data.Timeline || []} filename="historico-aluno" /></> : selected ? <Loading /> : <Empty title="Nenhum aluno" />}</section>;
}
