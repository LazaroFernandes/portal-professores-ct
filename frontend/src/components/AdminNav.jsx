import { NavLink } from "react-router-dom";
import { CalendarCheck, ClipboardList, Users } from "lucide-react";
import { useAuth } from "../auth/AuthContext";

export function AdminNav() {
  const { session } = useAuth();
  if (!session) return null;
  return <nav className="admin-nav" aria-label="Navegação administrativa">
    <NavLink to="/academia"><Users size={17} />Operação diária</NavLink>
    {session.role === "admin" && <><NavLink to="/vencimentos"><CalendarCheck size={17} />Vencimentos</NavLink>
    <NavLink to="/admin/professores"><Users size={17} />Análise dos professores</NavLink></>}
    <NavLink to="/registro"><ClipboardList size={17} />Registro semanal</NavLink>
  </nav>;
}
