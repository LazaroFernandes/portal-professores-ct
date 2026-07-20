import { useMemo, useState } from "react";
import { Download, Search } from "lucide-react";

function csvEscape(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function DataTable({ rows = [], columns, filename = "dados", searchable = true }) {
  const [search, setSearch] = useState("");
  const visibleColumns = columns || (rows[0] ? Object.keys(rows[0]).map((key) => ({ key, label: key })) : []);
  const filtered = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("pt-BR");
    if (!term) return rows;
    return rows.filter((row) => visibleColumns.some(({ key }) => String(row[key] ?? "").toLocaleLowerCase("pt-BR").includes(term)));
  }, [rows, search, visibleColumns]);

  function download() {
    const content = [visibleColumns.map(({ label }) => csvEscape(label)).join(","), ...filtered.map((row) => visibleColumns.map(({ key }) => csvEscape(row[key])).join(","))].join("\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob(["\ufeff", content], { type: "text/csv;charset=utf-8" }));
    link.download = `${filename}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  if (!rows.length) return <div className="empty-inline">Nenhum registro encontrado.</div>;
  return <div className="table-card">
    <div className="table-toolbar">
      {searchable && <label className="search-field"><Search size={16} /><input aria-label="Buscar na tabela" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar…" /></label>}
      <button className="button ghost" onClick={download}><Download size={16} /> Exportar CSV</button>
    </div>
    <div className="table-scroll"><table><thead><tr>{visibleColumns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead><tbody>
      {filtered.map((row, index) => <tr key={row.client_id || row.ClienteId || row.CodigoCliente || index}>{visibleColumns.map((column) => <td key={column.key}>{column.render ? column.render(row[column.key], row) : String(row[column.key] ?? "")}</td>)}</tr>)}
    </tbody></table></div>
    <div className="table-count">{filtered.length} de {rows.length} registros</div>
  </div>;
}
