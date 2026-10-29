import { NavLink } from "react-router-dom";
import { CalendarCheck, ClipboardList, Users } from "lucide-react";
import { useAuth } from "../auth/AuthContext";

export function AdminNav() {
  const { session } = useAuth();
  if (!session) return null;
  return <nav className="admin-nav" aria-label="Navegação administrativa">
    <NavLink to="/academia"><Users size={17} />Registro diário</NavLink>
    {session.role === "admin" && <><NavLink to="/vencimentos"><CalendarCheck size={17} />Vencimentos</NavLink>
    <NavLink to="/admin/financeiro">Financeiro</NavLink>
    <NavLink to="/admin/horarios">Horários e salários</NavLink>
    <NavLink to="/admin/professores"><Users size={17} />Análise diária</NavLink></>}
    <NavLink to="/acoes"><ClipboardList size={17} />Ações e retornos</NavLink>
    <NavLink to="/pendencias">Pendências</NavLink>
    {session.role === "admin" && <NavLink to="/admin/historico-semanal">Histórico semanal</NavLink>}
  </nav>;
}
