import { ChevronLeft, ChevronRight, LogOut, RefreshCw, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { AdminNav } from "../components/AdminNav";
import { Empty, ErrorState, Loading } from "../components/AsyncState";
import { Kpi, KpiGrid } from "../components/Kpi";
import { currentWeek, filterStudents, shiftWeek, weekStart } from "./professorAnalysisUtils";

const percent = (value) => `${value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
const dateLabel = (value) => new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(`${value}T12:00:00Z`));
const statusLabels = { complete: "Completo", partial: "Parcial", empty: "Em branco" };

export function ProfessorAnalysisPage() {
  const { logout } = useAuth();
  const [start, setStart] = useState(currentWeek);
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const [professor, setProfessor] = useState("all");
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [order, setOrder] = useState("filled_pct");

  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true, data: null, error: null });
    api(`/api/admin/professors/analysis?start=${start}`, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) {
          setState({ loading: false, data, error: null });
          setProfessor((selected) => selected === "all" || data.professors.some((row) => row.name === selected) ? selected : "all");
        }
      })
      .catch((error) => { if (!controller.signal.aborted) setState({ loading: false, data: null, error }); });
    return () => controller.abort();
  }, [start, revision]);

  const { data, loading, error } = state;
  const end = new Date(new Date(`${start}T12:00:00Z`).getTime() + 6 * 86400000).toISOString().slice(0, 10);
  const students = useMemo(() => filterStudents(data?.students || [], { professor, status, search }), [data, professor, status, search]);
  const professors = useMemo(() => [...(data?.professors || [])].sort((a, b) => (
    order === "name" ? (a.name || "Sem professor").localeCompare(b.name || "Sem professor", "pt-BR")
      : (order === "pending" ? b.pending - a.pending : a.filled_pct - b.filled_pct) || a.name.localeCompare(b.name, "pt-BR")
  )), [data, order]);

  function chooseWeek(value) {
    const next = weekStart(value);
    if (next) setStart(next);
  }

  return <div className="page professor-analysis">
    <AdminNav />
    <header className="page-heading">
      <div><span className="eyebrow">GESTÃO DA EQUIPE</span><h1>Histórico semanal</h1>
        <p>Consulta dos registros antigos. Novos acompanhamentos são feitos exclusivamente no registro diário.</p></div>
      <div className="frequency-actions">
        <button className="button ghost" onClick={logout}><LogOut size={17} />Sair</button>
        <button className="button primary" disabled={loading} onClick={() => setRevision((n) => n + 1)}><RefreshCw size={17} className={loading ? "spin" : ""} />Atualizar análise</button>
      </div>
    </header>
    <section className="analysis-period" aria-label="Período de análise">
      <div className="analysis-week">
        <button className="button" aria-label="Semana anterior" onClick={() => setStart(shiftWeek(start, -1))}><ChevronLeft size={18} /></button>
        <label>Semana de referência<input type="date" value={start} onChange={(event) => chooseWeek(event.target.value)} /></label>
        <button className="button" aria-label="Próxima semana" onClick={() => setStart(shiftWeek(start, 1))}><ChevronRight size={18} /></button>
        <button className="button ghost" onClick={() => setStart(currentWeek())}>Semana atual</button>
      </div>
      <p>De {dateLabel(start)} a {dateLabel(end)}</p>
    </section>
    {loading ? <Loading label="Lendo carteiras e registros da semana…" /> : error ? <ErrorState error={error} retry={() => setRevision((n) => n + 1)} /> : data && <>
      {data.available_weeks.length > 0 && <label className="analysis-history-select">Consultar uma semana com registros
        <select value={data.available_weeks.includes(start) ? start : ""} onChange={(event) => { if (event.target.value) setStart(event.target.value); }}>
          <option value="">Selecionar semana registrada</option>
          {data.available_weeks.map((week) => <option key={week} value={week}>Semana de {dateLabel(week)}</option>)}
        </select>
      </label>}
      {data.summary.total > 0 && data.summary.not_opened === data.summary.total && <div className="notice warning" role="status">Nenhum registro foi aberto para a carteira ativa nesta semana. {data.available_weeks.length ? "Use a lista de semanas registradas para consultar o histórico." : "Ainda não há semanas registradas na base."}</div>}
      <p className="analysis-context">Visão da <strong>carteira ativa atual</strong>, inclusive ao consultar semanas anteriores. Preenchimento indica registro de acompanhamento; não comprova contato realizado com o aluno.</p>
      <KpiGrid>
        <Kpi label="Alunos ativos" value={data.summary.total} detail={`${data.summary.professors} professores · sem professor: ${data.summary.unassigned}`} />
        <Kpi label="Com preenchimento" value={percent(data.summary.filled_pct)} detail={`${data.summary.filled} de ${data.summary.total} alunos · pelo menos um campo`} />
        <Kpi label="Completos" value={data.summary.complete} tone="good" detail={`${percent(data.summary.complete_pct)} · os três campos preenchidos`} />
        <Kpi label="Parciais" value={data.summary.partial} tone="warning" detail="Um ou dois campos preenchidos" />
        <Kpi label="Em branco" value={data.summary.empty} tone="warning" detail={`${data.summary.not_opened} sem registro aberto nesta semana`} />
      </KpiGrid>
      {Boolean(data.quality.duplicate_students || data.quality.duplicate_records || data.quality.invalid_students) && <div className="notice warning" role="status">
        A base contém {data.quality.duplicate_students} cadastros duplicados, {data.quality.duplicate_records} registros semanais duplicados e {data.quality.invalid_students} cadastros sem identificador válido. Cada aluno é contado uma vez; cadastros inválidos ficam fora da análise.
      </div>}
      {!data.summary.total ? <Empty title="Nenhum aluno ativo na base de acompanhamento" text="Confira a atualização da carteira de alunos antes de avaliar os professores." /> : <>
        <section className="panel analysis-section" aria-labelledby="professors-title">
          <div className="analysis-section-heading"><div><h2 id="professors-title">Visão por professor</h2><p>Selecione um professor para filtrar a lista de alunos abaixo.</p></div>
            <label>Ordenar por<select value={order} onChange={(event) => setOrder(event.target.value)}><option value="filled_pct">Menor preenchimento</option><option value="pending">Mais registros a concluir</option><option value="name">Nome do professor</option></select></label>
          </div>
          <div className="table-scroll analysis-table"><table>
            <caption className="analysis-sr-only">Acompanhamento semanal por professor responsável atual</caption>
            <thead><tr><th>Professor</th><th>Alunos</th><th>Preenchidos</th><th>Completos</th><th>Parciais</th><th>Em branco</th><th>Preenchimento</th></tr></thead>
            <tbody>{professors.map((row) => <tr key={row.name} className={professor === row.name ? "analysis-selected" : ""}>
              <td><button className="analysis-professor-link" aria-pressed={professor === row.name} onClick={() => { setProfessor(row.name); setSearch(""); setStatus("all"); }}>{row.name || "Sem professor"}</button></td>
              <td>{row.total}</td><td>{row.filled}</td><td>{row.complete}</td><td>{row.partial}</td><td>{row.empty}</td>
              <td><div className="analysis-progress"><progress value={row.filled_pct} max="100" aria-label={`Preenchimento de ${row.name || "alunos sem professor"}`} /><strong>{percent(row.filled_pct)}</strong></div></td>
            </tr>)}</tbody>
          </table></div>
        </section>
        <section className="panel analysis-section" aria-labelledby="students-title">
          <div className="analysis-section-heading"><div><h2 id="students-title">Lista de controle dos alunos</h2><p>Alunos nos filtros selecionados: {students.length}.</p></div>
            {professor !== "all" && professor !== "" && <Link className="button" to={`/registro?${new URLSearchParams({ start: data.start, professor })}`}><Users size={17} />Abrir registro do professor</Link>}
          </div>
          <div className="analysis-filters">
            <label>Professor<select value={professor} onChange={(event) => setProfessor(event.target.value)}><option value="all">Todos os professores</option>{data.professors.map((row) => <option key={row.name} value={row.name}>{row.name || "Sem professor"}</option>)}</select></label>
            <label>Situação do registro<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">Todos os registros</option><option value="pending">A concluir (parciais e em branco)</option><option value="complete">Completos</option><option value="partial">Parciais</option><option value="empty">Em branco</option></select></label>
            <label>Pesquisar<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Aluno, professor ou modalidade" /></label>
          </div>
          {!students.length ? <Empty text="Nenhum aluno corresponde aos filtros selecionados." /> : <div className="table-scroll analysis-table analysis-students"><table>
            <thead><tr><th>Aluno / responsável</th><th>Situação</th><th>Frequência informada</th><th>Desempenho</th><th>Relato e histórico</th></tr></thead>
            <tbody>{students.map((student) => <tr key={student.client_id}>
              <td><strong>{student.name || "Nome não informado"}</strong><small>{student.professor || "Sem professor"}</small><small>{[student.shift, student.modality].filter(Boolean).join(" · ")}</small></td>
              <td><span className={`analysis-badge ${student.status}`}>{statusLabels[student.status]}</span>{!student.record_exists && <small>Semana não aberta</small>}</td>
              <td>{student.frequency || "—"}</td><td>{student.performance || "—"}</td>
              <td>{student.report ? <details><summary>Ver relato</summary><p className="analysis-report">{student.report}</p></details> : <span className="muted">Sem relato</span>}
                {student.updated_at && <small>Atualizado em {student.updated_at}</small>}
                {student.record_professor && student.record_professor !== student.professor && <small>Professor no registro: {student.record_professor}</small>}
              </td>
            </tr>)}</tbody>
          </table></div>}
        </section>
      </>}
      <footer className="analysis-footnote">Fonte: {data.source} · Consulta em {new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo" }).format(new Date(data.read_at))}.
        {data.quality.records_outside_current_portfolio > 0 && ` ${data.quality.records_outside_current_portfolio} registros da semana estão fora da carteira ativa atual e não entram nos indicadores.`}
        <br />A data da consulta não indica a última sincronização da carteira.</footer>
    </>}
  </div>;
}
