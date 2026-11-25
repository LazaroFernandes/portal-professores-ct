import { RefreshCw, Search, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import "../styles/professor-students.css";
import { query } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, Loading } from "../components/AsyncState";
import { Kpi, KpiGrid } from "../components/Kpi";

function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

export function ProfessorStudentsPage() {
  const { session } = useAuth();
  const [request, setRequest] = useState({ professor: "", refresh: false });
  const professor = request.professor;
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState("");
  const [shiftFilter, setShiftFilter] = useState("all");
  const [modalityFilter, setModalityFilter] = useState("all");

  useEffect(() => {
    let active = true;
    setError(null);
    if (request.refresh) setRefreshing(true);
    else setLoading(true);
    query("/api/professor/students", {
      professor: request.professor,
      refresh: request.refresh || undefined,
    }).then((payload) => {
      if (active) setData(payload);
    }).catch((reason) => {
      if (active) setError(reason);
    }).finally(() => {
      if (active) {
        setLoading(false);
        setRefreshing(false);
      }
    });
    return () => { active = false; };
  }, [request]);

  const students = data?.students || [];
  const modalities = useMemo(() => {
    const values = new Set();
    students.forEach((student) => {
      if (student.modality) values.add(student.modality);
    });
    return Array.from(values).sort((a, b) => a.localeCompare(b, "pt-BR"));
  }, [students]);

  const filtered = useMemo(() => {
    const term = normalizeText(search.trim());
    return students.filter((student) => {
      if (shiftFilter === "unassigned" && ["MANHÃ", "TARDE", "NOITE"].includes(student.shift.toUpperCase())) return false;
      if (shiftFilter !== "all" && shiftFilter !== "unassigned" && student.shift.toUpperCase() !== shiftFilter) {
        return false;
      }
      if (modalityFilter !== "all" && student.modality !== modalityFilter) return false;
      if (!term) return true;
      return (
        normalizeText(student.name).includes(term)
        || normalizeText(student.plan).includes(term)
        || normalizeText(student.modality).includes(term)
        || String(student.client_id).includes(term)
      );
    });
  }, [students, search, shiftFilter, modalityFilter]);

  const hasActiveFilters = Boolean(search.trim()) || shiftFilter !== "all" || modalityFilter !== "all";
  const selectedProfessor = professor || data?.professor || "";

  function clearFilters() {
    setSearch("");
    setShiftFilter("all");
    setModalityFilter("all");
  }

  if (loading && !data) {
    return <div className="page students-page"><Loading label="Carregando lista de alunos..." /></div>;
  }
  if (error && !data) {
    return <div className="page students-page"><ErrorState error={error} retry={() => setRequest({ professor, refresh: false })} /></div>;
  }

  const summary = data?.summary || { total: 0, morning: 0, afternoon: 0, evening: 0, unassigned: 0 };

  return <div className="page students-page">
    <div className="page-heading">
      <div>
        <h1>{session.role === "admin" ? "Lista de alunos" : "Meus alunos"}</h1>
        <p>Alunos ativos da carteira de {data?.professor || session.name}.</p>
      </div>
      <div>
        <button className="button ghost" onClick={() => setRequest({ professor, refresh: true })} disabled={refreshing}>
          <RefreshCw size={17} className={refreshing ? "spin" : ""} />
          {refreshing ? "Atualizando..." : "Atualizar"}
        </button>
      </div>
    </div>

    {error && <div className="notice error presence-notice">Não foi possível atualizar a lista: {error.message}</div>}

    {session.role === "admin" && data?.professors?.length > 0 && (
      <div className="filter-bar students-professor">
        <label>
          Professor
          <select value={selectedProfessor} onChange={(event) => {
            setData(null);
            setLoading(true);
            setRequest({ professor: event.target.value, refresh: false });
            clearFilters();
          }}>
            {data.professors.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
        <div>
          <strong>{data.total}</strong>
          <span>{data.total === 1 ? "aluno na lista" : "alunos na lista"}</span>
        </div>
      </div>
    )}

    <KpiGrid>
      <Kpi label="Total na lista" value={summary.total} />
      <Kpi label="Manhã" value={summary.morning} />
      <Kpi label="Tarde" value={summary.afternoon} />
      <Kpi label="Noite" value={summary.evening} />
      {summary.unassigned > 0 && <Kpi label="Sem turno" value={summary.unassigned} tone="warning" />}
    </KpiGrid>

    {!students.length ? (
      <section className="state-card presence-empty">
        <Users size={34} />
        <strong>Nenhum aluno ativo nesta lista</strong>
        <p>Não há alunos ativos vinculados a {data?.professor || session.name} no momento.</p>
      </section>
    ) : (
      <>
        <div className="filter-bar students-filter-bar">
          <label className="students-search">
            Pesquisar aluno
            <div className="search-field students-search-field">
              <Search size={16} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Nome, plano ou código..."
              />
            </div>
          </label>
          <label>
            Turno
            <select value={shiftFilter} onChange={(event) => setShiftFilter(event.target.value)}>
              <option value="all">Todos os turnos</option>
              <option value="MANHÃ">Manhã</option>
              <option value="TARDE">Tarde</option>
              <option value="NOITE">Noite</option>
              <option value="unassigned">Não informado</option>
            </select>
          </label>
          {modalities.length > 0 && (
            <label>
              Modalidade
              <select value={modalityFilter} onChange={(event) => setModalityFilter(event.target.value)}>
                <option value="all">Todas as modalidades</option>
                {modalities.map((modality) => <option key={modality} value={modality}>{modality}</option>)}
              </select>
            </label>
          )}
          <div className="students-filter-meta">
            <strong>{filtered.length}</strong>
            <span>{filtered.length === 1 ? "aluno exibido" : "alunos exibidos"}{hasActiveFilters ? ` de ${students.length}` : ""}</span>
          </div>
          {hasActiveFilters && (
            <button className="button ghost small" type="button" onClick={clearFilters}>
              Limpar filtros
            </button>
          )}
        </div>

        {!filtered.length ? (
          <section className="state-card presence-empty">
            <Users size={34} />
            <strong>Nenhum aluno encontrado</strong>
            <p>Ajuste a pesquisa ou limpe os filtros para ver todos os alunos da sua lista.</p>
            <button className="button ghost" type="button" onClick={clearFilters}>Limpar filtros</button>
          </section>
        ) : (
          <div className="table-card students-portfolio-table">
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Aluno</th>
                    <th>Turno</th>
                    <th>Modalidade</th>
                    <th>Plano</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((student) => (
                    <tr key={student.client_id}>
                      <td data-label="Aluno">
                        <div><strong>{student.name}</strong><small className="table-subtext">Código {student.client_id}</small></div>
                      </td>
                      <td data-label="Turno">
                        {student.shift
                          ? <span className="shift-pill">{student.shift}</span>
                          : <span className="missing-value">Não informado</span>}
                      </td>
                      <td data-label="Modalidade">
                        {student.modality || <span className="missing-value">Não informada</span>}
                      </td>
                      <td data-label="Plano">
                        {student.plan || <span className="missing-value">Não informado</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </>
    )}
  </div>;
}
