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

export function FrequencyPage() {
  const { logout } = useAuth();
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [showInactive, setShowInactive] = useState(false);
  const [search, setSearch] = useState("");

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

  const students = payload?.snapshot?.inactive_students || [];
  const filtered = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("pt-BR");
    if (!term) return students;
    const digits = term.replace(/\D/g, "");
    return students.filter((student) => (
      student.name.toLocaleLowerCase("pt-BR").includes(term)
      || (digits && student.phone.replace(/\D/g, "").includes(digits))
    ));
  }, [search, students]);

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
          <div><span>Ativos</span><strong>{snapshot.active_count}</strong></div>
          <p>Alunos ativos no sistema e sem pagamento vencido.</p>
        </article>
        <article className="frequency-card inactive">
          <div className="frequency-card-icon"><UserX /></div>
          <div><span>Inativos</span><strong>{snapshot.inactive_count}</strong></div>
          <p>Alunos com pagamento vencido há 3 dias ou mais.</p>
          <button className="button ghost" onClick={() => setShowInactive((visible) => !visible)}>
            Ver planos vencidos <ChevronDown size={17} className={showInactive ? "rotated" : ""} />
          </button>
        </article>
      </div>

      {showInactive && <section className="panel inactive-panel">
        <div className="section-title">
          <div><h2>Planos vencidos</h2><p>{students.length} alunos fora do período de tolerância.</p></div>
        </div>
        {!students.length ? <div className="empty-inline">Não há planos vencidos há 3 dias ou mais.</div> : <>
          <label className="search-field frequency-search">
            <Search size={16} />
            <input
              aria-label="Pesquisar por nome ou telefone"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Pesquisar por nome ou telefone"
            />
          </label>
          {!filtered.length ? <div className="empty-inline">Nenhum aluno encontrado para esta pesquisa.</div> :
            <div className="table-scroll frequency-table"><table>
              <thead><tr><th>NOME</th><th>PLANO</th><th>VENCIMENTO</th><th>TELEFONE</th></tr></thead>
              <tbody>{filtered.map((student) => <tr key={student.client_id}>
                <td data-label="Nome">{student.name || "Não informado"}</td>
                <td data-label="Plano">{student.plan || "Não informado"}</td>
                <td data-label="Vencimento">{student.due_date ? dueDate.format(new Date(`${student.due_date}T00:00:00Z`)) : "Não informado"}</td>
                <td data-label="Telefone">{student.phone || "Não informado"}</td>
              </tr>)}</tbody>
            </table></div>}
        </>}
      </section>}
    </>}
  </div>;
}
