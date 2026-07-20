import { RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { ErrorState, Loading } from "../components/AsyncState";
import { DataTable } from "../components/DataTable";
import { Kpi, KpiGrid } from "../components/Kpi";

const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export function MondayPage() {
  const [payload, setPayload] = useState(null); const [error, setError] = useState(null); const [tab, setTab] = useState("tasks"); const [refreshing, setRefreshing] = useState(false);
  const load = () => api("/api/admin/monday").then(setPayload).catch(setError);
  useEffect(load, []);
  async function refresh() { setRefreshing(true); try { setPayload(await api("/api/admin/monday/refresh", { method: "POST" })); } catch (reason) { setError(reason); } finally { setRefreshing(false); } }
  if (error) return <div className="page"><ErrorState error={error} retry={load} /></div>;
  if (!payload) return <div className="page"><Loading /></div>;
  if (!payload.available) return <div className="page"><div className="page-heading"><div><h1>Painel de segunda</h1><p>O snapshot ainda não foi gerado.</p></div></div><button className="button primary" onClick={refresh}>{refreshing ? "Gerando…" : "Gerar painel agora"}</button></div>;
  const snap = payload.snapshot; const view = snap.visao_geral; const financial = snap.financeiro;
  return <div className="page">
    <div className="page-heading"><div><span className="eyebrow">COCKPIT SEMANAL</span><h1>Painel de segunda</h1><p>Dados de {snap.data_ref} · atualizado em {new Date(snap.gerado_em).toLocaleString("pt-BR")}</p></div><button className="button primary" onClick={refresh} disabled={refreshing}><RefreshCw size={17} className={refreshing ? "spin" : ""} />{refreshing ? "Atualizando…" : "Atualizar"}</button></div>
    <KpiGrid><Kpi label="Alunos ativos" value={view.ativos} detail={`${view.variacao_7d >= 0 ? "+" : ""}${view.variacao_7d} vs 7 dias`} /><Kpi label="Novos (7d)" value={view.clientes_novos_7d} tone="good" /><Kpi label="Perdidos (30d)" value={view.perdidos_30d} tone="danger" /><Kpi label="Churn (30d)" value={`${view.churn_30d_pct}%`} tone={view.churn_30d_pct >= 8 ? "warning" : "good"} /><Kpi label="MRR ativo" value={money.format(view.mrr)} detail={`Ticket ${money.format(view.ticket_medio)}`} /></KpiGrid>
    <KpiGrid><Kpi label="Receita perdida (60d)" value={money.format(view.receita_perdida_60d)} tone="danger" /><Kpi label={`Receitas ${financial.mes}`} value={money.format(financial.receitas)} tone="good" /><Kpi label="Despesas" value={money.format(financial.despesas)} /><Kpi label="Saldo" value={money.format(financial.saldo)} tone={financial.saldo >= 0 ? "good" : "danger"} /><Kpi label="A receber vencido" value={money.format(financial.receber_vencido)} tone="warning" /></KpiGrid>
    <div className="subnav">{[["tasks", "Tarefas"], ["action", "Ligar hoje"], ["new", "Novos e sem professor"], ["churn", "Churn 60d"], ["modalities", "Modalidades"], ["professors", "Professores"], ["financial", "Financeiro"]].map(([value, label]) => <button key={value} className={tab === value ? "active" : ""} onClick={() => setTab(value)}>{label}</button>)}</div>
    {tab === "tasks" && <Tasks payload={payload} reload={load} />}
    {tab === "action" && <Lists lists={[["Ativos sem vir há 30+ dias", snap.ligar_hoje.sem_vir_30d, "sem-vir-30d"], ["Queda de frequência", snap.ligar_hoje.sem_vir_7d_queda, "queda"], ["Renovação esta semana", snap.ligar_hoje.vencendo_7d_acao, "renovacoes"]]} />}
    {tab === "new" && <Lists lists={[["Novos e reativados", snap.novos_reativados, "novos"], ["Ativos sem professor", snap.sem_professor.filter((item) => item.modalidade !== "FUNCIONARIOS"), "sem-professor"]]} />}
    {tab === "churn" && <Lists lists={[["Perdidos nos últimos 60 dias", snap.churn_60d, "churn-60d"]]} />}
    {tab === "modalities" && <ChartTable title="Alunos por modalidade" rows={snap.modalidades} label="modalidade" value="ativos" />}
    {tab === "professors" && <ChartTable title="Carteira por professor" rows={snap.professores} label="professor" value="ativos" />}
    {tab === "financial" && <ChartTable title="Receitas nos últimos seis meses" rows={financial.receitas_6m} label="mes" value="valor" />}
  </div>;
}

function Tasks({ payload, reload }) {
  const [text, setText] = useState(""); const tasks = payload.tasks;
  async function toggleAuto(id, done) { await api(`/api/admin/monday/tasks/auto/${id}`, { method: "PUT", body: JSON.stringify({ done }) }); reload(); }
  async function toggleManual(id, done) { await api(`/api/admin/monday/tasks/manual/${id}`, { method: "PUT", body: JSON.stringify({ done }) }); reload(); }
  async function add(event) { event.preventDefault(); if (!text.trim()) return; await api("/api/admin/monday/tasks/manual", { method: "POST", body: JSON.stringify({ text }) }); setText(""); reload(); }
  async function remove(id) { await api(`/api/admin/monday/tasks/manual/${id}`, { method: "DELETE" }); reload(); }
  const total = payload.auto_tasks.length + tasks.manual.length; const done = payload.auto_tasks.filter((item) => tasks.auto[item.id]).length + tasks.manual.filter((item) => item.done).length;
  return <section className="panel task-panel"><div className="section-title"><div><h2>Tarefas da semana</h2><p>{tasks.week} · reinicia toda segunda</p></div><strong>{done}/{total}</strong></div><div className="progress"><span style={{ width: `${total ? done / total * 100 : 0}%` }} /></div><h3>Ações sugeridas</h3>{payload.auto_tasks.map((item) => <label className="task" key={item.id}><input type="checkbox" checked={Boolean(tasks.auto[item.id])} onChange={(e) => toggleAuto(item.id, e.target.checked)} /><span>{item.text}</span></label>)}<h3>Minhas tarefas</h3>{tasks.manual.map((item) => <div className="task" key={item.id}><input type="checkbox" checked={Boolean(item.done)} onChange={(e) => toggleManual(item.id, e.target.checked)} /><span>{item.text || item.texto}</span><button onClick={() => remove(item.id)} aria-label="Remover tarefa"><Trash2 size={16} /></button></div>)}<form className="task-add" onSubmit={add}><input value={text} onChange={(e) => setText(e.target.value)} placeholder="Adicionar tarefa…" /><button className="button primary">Adicionar</button></form></section>;
}

function Lists({ lists }) { return <div className="section-stack">{lists.map(([title, rows, filename]) => <section className="panel" key={title}><div className="section-title"><h2>{title}</h2><span className="badge">{rows.length}</span></div><DataTable rows={rows} filename={filename} /></section>)}</div>; }

function ChartTable({ title, rows, label, value }) { return <section className="panel"><h2>{title}</h2><div className="chart"><ResponsiveContainer width="100%" height={Math.max(280, rows.length * 46)}><BarChart data={rows} layout="vertical"><CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" /><YAxis dataKey={label} type="category" width={150} tick={{ fontSize: 12 }} /><Tooltip /><Bar dataKey={value} fill="#f59e0b" radius={[0, 6, 6, 0]} /></BarChart></ResponsiveContainer></div><DataTable rows={rows} filename={title.toLowerCase().replaceAll(" ", "-")} /></section>; }
