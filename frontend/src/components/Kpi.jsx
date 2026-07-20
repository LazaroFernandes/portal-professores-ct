export function Kpi({ label, value, detail, tone = "default" }) {
  return <article className={`kpi ${tone}`}><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article>;
}

export function KpiGrid({ children }) {
  return <div className="kpi-grid">{children}</div>;
}
