import { Activity, CalendarCheck, ClipboardList, Dumbbell, LogOut, Menu, Target, Users, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const adminLinks = [
  ["/admin/retencao", Activity, "Retenção"],
  ["/admin/segunda", CalendarCheck, "Painel de segunda"],
  ["/admin/crm", Target, "Retorno e CRM"],
  ["/admin/treinos", Dumbbell, "Evolução de treinos"],
  ["/registro", ClipboardList, "Registro semanal"],
];

export function Layout() {
  const { session, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const links = session.role === "admin" ? adminLinks : [["/registro", Users, "Meus alunos"]];
  return <div className="app-shell">
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <div className="brand"><div className="brand-mark">CT</div><div><strong>Ítalo Vieira</strong><span>Portal da equipe</span></div><button className="mobile-close" onClick={() => setOpen(false)}><X /></button></div>
      <nav>{links.map(([to, Icon, label]) => <NavLink key={to} to={to} onClick={() => setOpen(false)}><Icon size={19} />{label}</NavLink>)}</nav>
      <div className="sidebar-footer"><div><span>{session.role === "admin" ? "Administrador" : "Professor"}</span><strong>{session.name}</strong></div><button onClick={logout} title="Sair"><LogOut size={18} /></button></div>
    </aside>
    {open && <button className="backdrop" onClick={() => setOpen(false)} aria-label="Fechar menu" />}
    <main className="main"><header className="mobile-header"><button onClick={() => setOpen(true)}><Menu /></button><strong>CT Ítalo Vieira</strong></header><Outlet /></main>
  </div>;
}
