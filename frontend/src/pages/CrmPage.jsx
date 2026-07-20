import { Phone, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { ErrorState, Loading } from "../components/AsyncState";
import { DataTable } from "../components/DataTable";
import { Kpi, KpiGrid } from "../components/Kpi";

const tabs = [
  ["actions", "Lista de ação"], ["alerts", "Alerta 7 dias"], ["renewals", "Renovações"],
  ["onboarding", "Onboarding"], ["dates", "Datas"], ["without_professor", "Sem professor"],
  ["contacts", "Contatos"], ["metrics", "Tendência"], ["charts", "Gráficos"],
];
const filterFields = ["BucketAcao", "Bucket", "Professor", "Modalidade", "Contrato", "Urgencia", "Saude", "Status", "Origem", "Operador"];

export function CrmPage() {
  const [data, setData] = useState(null); const [error, setError] = useState(null); const [tab, setTab] = useState("actions"); const [filters, setFilters] = useState({}); const [contact, setContact] = useState(null);
  const load = () => api("/api/admin/crm").then(setData).catch(setError);
  useEffect(load, []);
  useEffect(() => setFilters({}), [tab]);
  if (error) return <div className="page"><ErrorState error={error} retry={load} /></div>;
  if (!data) return <div className="page"><Loading /></div>;
  if (tab === "charts") return <PageShell tab={tab} setTab={setTab}><CrmCharts actions={data.actions} /></PageShell>;
  const rows = data[tab] || [];
  const availableFilters = filterFields.filter((field) => rows.some((row) => row[field] !== undefined && row[field] !== ""));
  const filtered = rows.filter((row) => Object.entries(filters).every(([field, value]) => !value || String(row[field] ?? "") === value));
  const canContact = ["actions", "alerts", "renewals", "onboarding"].includes(tab);
  const columns = rows[0] ? Object.keys(rows[0]).slice(0, 14).map((key) => ({ key, label: key })) : [];
  if (canContact) columns.push({ key: "_action", label: "Ação", render: (_, row) => <button className="button small" onClick={() => setContact({ row, source: tab })}><Phone size={15} /> Registrar</button> });
  return <PageShell tab={tab} setTab={setTab}>
    <KpiGrid><Kpi label="Lista de ação" value={data.actions.length} /><Kpi label="Alertas" value={data.alerts.length} tone="danger" /><Kpi label="Renovações" value={data.renewals.length} tone="warning" /><Kpi label="Contatos registrados" value={data.contacts.length} tone="good" /></KpiGrid>
    {availableFilters.length > 0 && <div className="filter-bar">{availableFilters.map((field) => <label key={field}>{field}<select value={filters[field] || ""} onChange={(e) => setFilters({ ...filters, [field]: e.target.value })}><option value="">Todos</option>{[...new Set(rows.map((row) => String(row[field] ?? "")).filter(Boolean))].sort().map((value) => <option key={value}>{value}</option>)}</select></label>)}</div>}
    <DataTable rows={filtered} columns={columns} filename={`crm-${tab}`} />
    {contact && <ContactModal contact={contact} close={() => setContact(null)} saved={() => { setContact(null); load(); }} />}
  </PageShell>;
}

function PageShell({ tab, setTab, children }) { return <div className="page"><div className="page-heading"><div><span className="eyebrow">RETENÇÃO ATIVA</span><h1>Retorno e CRM</h1><p>Prioridades, renovações e histórico de contatos.</p></div></div><div className="subnav">{tabs.map(([value, label]) => <button key={value} className={tab === value ? "active" : ""} onClick={() => setTab(value)}>{label}</button>)}</div>{children}</div>; }

function ContactModal({ contact, close, saved }) {
  const row = contact.row; const [form, setForm] = useState({ status: "Pendente", notes: "", operator: "" }); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const clientId = Number(row.CodigoCliente || row.ClienteId || row.codigo || 0); const name = row.NomeCliente || row.Nome || row.nome || `#${clientId}`;
  async function submit(event) { event.preventDefault(); setBusy(true); setError(""); try { await api("/api/admin/crm/contacts", { method: "POST", body: JSON.stringify({ client_id: clientId, client_name: name, source: contact.source, ...form }) }); saved(); } catch (reason) { setError(reason.message); } finally { setBusy(false); } }
  return <div className="modal-backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && close()}><form className="modal" onSubmit={submit}><button type="button" className="modal-close" onClick={close}><X /></button><h2>Registrar contato</h2><p><strong>{name}</strong> · #{clientId}</p>{error && <div className="notice error">{error}</div>}<label>Resultado<select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>{["Pendente", "Falou - vai voltar", "Falou - cancelou", "Sem resposta", "Outro"].map((value) => <option key={value}>{value}</option>)}</select></label><label>Observação<textarea rows="4" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label><label>Operador<input required value={form.operator} onChange={(e) => setForm({ ...form, operator: e.target.value })} /></label><button className="button primary" disabled={busy}>{busy ? "Salvando…" : "Salvar contato"}</button></form></div>;
}

function CrmCharts({ actions }) {
  const buckets = useMemo(() => Object.entries(actions.reduce((acc, row) => { const key = row.BucketAcao || row.Bucket || "Sem bucket"; acc[key] = (acc[key] || 0) + 1; return acc; }, {})).map(([name, value]) => ({ name, value })), [actions]);
  const professors = useMemo(() => Object.entries(actions.reduce((acc, row) => { const key = row.Professor || "Sem professor"; acc[key] = (acc[key] || 0) + 1; return acc; }, {})).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value), [actions]);
  return <div className="two-column"><Chart title="Por prioridade" data={buckets} /><Chart title="Risco por professor" data={professors} /></div>;
}

function Chart({ title, data }) { return <section className="panel"><h2>{title}</h2><ResponsiveContainer width="100%" height={320}><BarChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" tick={{ fontSize: 11 }} /><YAxis /><Tooltip /><Bar dataKey="value" fill="#f59e0b" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></section>; }
