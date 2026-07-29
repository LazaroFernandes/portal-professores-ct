import { ChevronDown, LogOut, RefreshCw, Search, Users, UserX } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, Loading } from "../components/AsyncState";


const updatedAt = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
  timeZone: "America/Sao_Paulo",
});
const dueDate = new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" });

function filterStudents(students, search) {
  const term = search.trim().toLocaleLowerCase("pt-BR");
  if (!term) return students;
  const digits = term.replace(/\D/g, "");
  return students.filter((student) => (
    student.name.toLocaleLowerCase("pt-BR").includes(term)
    || (digits && student.phone.replace(/\D/g, "").includes(digits))
  ));
}

function formatDate(value) {
  return value ? dueDate.format(new Date(`${value}T00:00:00Z`)) : "Não informado";
}

function formatOverdueDays(value) {
  if (value === null || value === undefined) return "Não informado";
  return value === 1 ? "1 dia em atraso" : `${value} dias em atraso`;
}

function formatDueDays(value) {
  if (value === null || value === undefined) return "Data não informada";
  if (value === 0) return "Vence hoje";
  if (value === 1) return "1 dia";
  if (value > 1) return `${value} dias`;
  const overdue = Math.abs(value);
  return overdue === 1 ? "Vencido há 1 dia (tolerância)" : `Vencido há ${overdue} dias (tolerância)`;
}

export function FrequencyPage() {
  const { logout } = useAuth();
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [showActive, setShowActive] = useState(false);
  const [showPending, setShowPending] = useState(false);
  const [activeSearch, setActiveSearch] = useState("");
  const [pendingSearch, setPendingSearch] = useState("");

  function load() {
    setError(null);
    return api("/api/admin/frequency").then(setPayload).catch(setError);
  }

  useEffect(() => { load(); }, []);

  async function refresh() {
    setRefreshing(true);
    setError(null);
    try {
      setPayload(await api("/api/admin/frequency/refresh", { method: "POST" }));
    } catch (reason) {
      setError(reason);
    } finally {
      setRefreshing(false);
    }
  }

  const activeStudents = payload?.snapshot?.active_students || [];
  const pendingStudents = payload?.snapshot?.inactive_students || [];
  const filteredActive = useMemo(
    () => filterStudents(activeStudents, activeSearch),
    [activeSearch, activeStudents],
  );
  const filteredPending = useMemo(
    () => filterStudents(pendingStudents, pendingSearch),
    [pendingSearch, pendingStudents],
  );

  if (!payload && !error) return <div className="page frequency-page"><Loading /></div>;

  const snapshot = payload?.snapshot;
  return <div className="page frequency-page">
    <div className="page-heading frequency-heading">
      <div>
        <span className="eyebrow">PLANOS</span>
        <h1>Controle de vencimento dos planos</h1>
        <p>{snapshot?.updated_at
          ? `Última atualização: ${updatedAt.format(new Date(snapshot.updated_at))}`
          : "Os dados ainda não foram processados."}</p>
      </div>
      <div className="frequency-actions">
        <button className="button ghost" onClick={logout}><LogOut size={17} /> Sair</button>
        <button className="button primary" onClick={refresh} disabled={refreshing}>
          <RefreshCw size={17} className={refreshing ? "spin" : ""} />
          {refreshing ? "Atualizando…" : "Atualizar agora"}
        </button>
      </div>
    </div>

    {error && <div className="notice error frequency-error" role="alert">
      <strong>Não foi possível atualizar os dados.</strong> {error.message}
    </div>}

    {!snapshot ? <section className="state-card frequency-empty">
      <strong>Nenhuma atualização disponível</strong>
      <p>Use “Atualizar agora” para gerar o primeiro resultado.</p>
    </section> : <>
      <div className="frequency-grid">
        <article className="frequency-card active">
          <div className="frequency-card-icon"><Users /></div>
          <div><span>Em dia</span><strong>{snapshot.active_count}</strong></div>
          <p>Alunos com contrato ativo e sem pendência fora da tolerância.</p>
          <button className="button ghost" onClick={() => setShowActive((visible) => !visible)}>
            Ver alunos em dia <ChevronDown size={17} className={showActive ? "rotated" : ""} />
          </button>
        </article>
        <article className="frequency-card inactive">
          <div className="frequency-card-icon"><UserX /></div>
          <div><span>Com pendência</span><strong>{snapshot.inactive_count}</strong></div>
          <p>Pagamentos ou planos vencidos fora da tolerância de 3 dias.</p>
          <button className="button ghost" onClick={() => setShowPending((visible) => !visible)}>
            Ver pendências <ChevronDown size={17} className={showPending ? "rotated" : ""} />
          </button>
        </article>
      </div>

      {showActive && <section className="panel frequency-panel">
        <div className="section-title">
          <div><h2>Alunos em dia</h2><p>{activeStudents.length} alunos com contrato ativo.</p></div>
        </div>
        {!activeStudents.length ? <div className="empty-inline">Não há alunos em dia para exibir.</div> : <>
          <label className="search-field frequency-search">
            <Search size={16} />
            <input
              aria-label="Pesquisar alunos em dia por nome ou telefone"
              value={activeSearch}
              onChange={(event) => setActiveSearch(event.target.value)}
              placeholder="Pesquisar por nome ou telefone"
            />
          </label>
          {!filteredActive.length ? <div className="empty-inline">Nenhum aluno encontrado para esta pesquisa.</div> :
            <div className="table-scroll frequency-table"><table>
              <thead><tr><th>NOME</th><th>PLANO ATUAL</th><th>VENCIMENTO / RENOVAÇÃO</th><th>PRAZO</th><th>TELEFONE</th></tr></thead>
              <tbody>{filteredActive.map((student) => <tr key={student.client_id}>
                <td data-label="Nome">{student.name || "Não informado"}</td>
                <td data-label="Plano atual">{student.plan || "Não informado"}</td>
                <td data-label="Vencimento / renovação">{formatDate(student.due_date)}</td>
                <td data-label="Prazo">{formatDueDays(student.days_until_due)}</td>
                <td data-label="Telefone">{student.phone || "Não informado"}</td>
              </tr>)}</tbody>
            </table></div>}
        </>}
      </section>}

      {showPending && <section className="panel frequency-panel">
        <div className="section-title">
          <div><h2>Alunos com pendência</h2><p>{pendingStudents.length} alunos fora do período de tolerância.</p></div>
        </div>
        {!pendingStudents.length ? <div className="empty-inline">Não há pendências fora da tolerância.</div> : <>
          <label className="search-field frequency-search">
            <Search size={16} />
            <input
              aria-label="Pesquisar por nome ou telefone"
              value={pendingSearch}
              onChange={(event) => setPendingSearch(event.target.value)}
              placeholder="Pesquisar por nome ou telefone"
            />
          </label>
          {!filteredPending.length ? <div className="empty-inline">Nenhum aluno encontrado para esta pesquisa.</div> :
            <div className="table-scroll frequency-table"><table>
              <thead><tr><th>NOME</th><th>PLANO ATUAL</th><th>VENCIMENTO</th><th>MOTIVO</th><th>ATRASO</th><th>TELEFONE</th></tr></thead>
              <tbody>{filteredPending.map((student) => <tr key={student.client_id}>
                <td data-label="Nome">{student.name || "Não informado"}</td>
                <td data-label="Plano atual">{student.plan || "Não informado"}</td>
                <td data-label="Vencimento">{formatDate(student.due_date)}</td>
                <td data-label="Motivo">{student.reason || "Pendência identificada"}</td>
                <td data-label="Atraso">{formatOverdueDays(student.days_overdue)}</td>
                <td data-label="Telefone">{student.phone || "Não informado"}</td>
              </tr>)}</tbody>
            </table></div>}
        </>}
      </section>}
    </>}
  </div>;
}
