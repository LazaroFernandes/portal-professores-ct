import { Activity, CalendarCheck, CalendarDays, ChartNoAxesColumn, ClipboardCheck, ClipboardList, Clock, History, ListTodo, Wallet } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const dailyLinks = [
  ["/academia", ClipboardCheck, "Registro diário"],
  ["/acoes", ClipboardList, "Ações e retornos"],
  ["/pendencias", ListTodo, "Pendências"],
];
const managementLinks = [
  ["/admin/professores", Activity, "Análise diária"],
  ["/admin/historico-semanal", History, "Histórico semanal"],
  ["/vencimentos", CalendarCheck, "Vencimentos"],
  ["/admin/financeiro", Wallet, "Financeiro"],
  ["/admin/horarios", CalendarDays, "Horários e salários"],
  ["/admin/simulacao", Clock, "Simulação de horários"],
  ["/admin/fluxo", ChartNoAxesColumn, "Fluxo e cobertura"],
];

function LinkGroup({ title, links, onNavigate }) {
  return <div className="portal-nav-group">
    <h2>{title}</h2>
    {links.map(([to, Icon, label]) => (
      <NavLink key={to} end to={to} onClick={onNavigate}>
        <Icon size={18} strokeWidth={1.7} aria-hidden="true" /><span>{label}</span>
      </NavLink>
    ))}
  </div>;
}

export function AdminNav({ onNavigate }) {
  const { session } = useAuth();
  if (!session) return null;
  return <nav className="portal-nav" aria-label="Navegação principal">
    <LinkGroup title="Atendimento" links={dailyLinks} onNavigate={onNavigate} />
    {session.role === "admin" && <LinkGroup title="Gestão" links={managementLinks} onNavigate={onNavigate} />}
  </nav>;
}
