import { LogOut, Menu, Moon, Sun, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { AdminNav } from "./AdminNav";
import "../styles/workspace.css";

const themeKey = "ct-professores-tema";
function initialTheme() {
  try { return localStorage.getItem(themeKey) === "dark" ? "dark" : "light"; }
  catch { return "light"; }
}

function MobileMenu({ name }) {
  const dialog = useRef(null);
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => {
    const panel = dialog.current;
    const desktop = window.matchMedia("(min-width: 701px)");
    const close = () => panel.close();
    close();
    desktop.addEventListener("change", close);
    return () => desktop.removeEventListener("change", close);
  }, [pathname]);

  return <>
    <button type="button" className="portal-menu-toggle" aria-haspopup="dialog" aria-controls="portal-menu" aria-expanded={open}
      onClick={() => { dialog.current.showModal(); setOpen(true); }}>
      <Menu size={18} aria-hidden="true" />Menu
    </button>
    <dialog id="portal-menu" className="portal-drawer" ref={dialog} aria-labelledby="portal-menu-title"
      onClose={() => setOpen(false)} onClick={event => {
        if (event.target === dialog.current && event.clientX >= dialog.current.getBoundingClientRect().right) dialog.current.close();
      }}>
      <div className="portal-drawer-head">
        <h2 id="portal-menu-title">Menu</h2>
        <button className="portal-icon" aria-label="Fechar menu" onClick={() => dialog.current.close()}><X size={20} /></button>
      </div>
      <p className="portal-drawer-account"><strong>{name}</strong> · Gerência</p>
      <AdminNav onNavigate={() => dialog.current.close()} />
    </dialog>
  </>;
}

export function Layout({ children }) {
  const { session, logout } = useAuth();
  const [theme, setTheme] = useState(initialTheme);
  const dark = theme === "dark";
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]').content = dark ? "#000000" : "#f2f2f7";
    try { localStorage.setItem(themeKey, theme); } catch { /* The theme is still applied for this visit. */ }
  }, [theme, dark]);
  const home = session ? (session.role === "admin" ? "/admin/professores" : "/academia") : "/login";
  const themeLabel = dark ? "Ativar tema claro" : "Ativar tema escuro";

  return <div className={`portal-workspace ${session ? "signed-in " + session.role : "guest"}`}>
    <a className="portal-skip" href="#portal-content">Pular para o conteúdo</a>
    <header className="portal-top">
      <Link to={home} className="portal-brand">CT <strong>Professores</strong></Link>
      {session && <span className="portal-account">{session.name} · {session.role === "admin" ? "Gerência" : "Professor"}</span>}
      <div className="portal-tools">
        <button className="portal-icon" title={themeLabel} aria-label={themeLabel} onClick={() => setTheme(dark ? "light" : "dark")}>
          {dark ? <Sun size={20} /> : <Moon size={20} />}
        </button>
        {session && <button type="button" className="portal-signout" onClick={logout}><LogOut size={16} aria-hidden="true" />Sair</button>}
        {session?.role === "admin" && <MobileMenu name={session.name} />}
      </div>
    </header>
    {session && <aside className="portal-side"><AdminNav /></aside>}
    <main id="portal-content" tabIndex={-1}>{children}</main>
  </div>;
}
