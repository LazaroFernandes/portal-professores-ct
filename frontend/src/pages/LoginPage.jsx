import { LockKeyhole } from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { session, login } = useAuth();
  const location = useLocation();
  const [demo, setDemo] = useState(false);
  useEffect(() => { fetch("/api/daily/preview-info").then(r => r.json()).then(d => setDemo(d.enabled)).catch(() => {}); }, []);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (session?.role === "admin") return <Navigate to={location.state?.from || "/admin/professores"} replace />;
  if (session?.role === "professor") return <Navigate to={location.state?.from || "/academia"} replace />;

  async function submit(event) {
    event.preventDefault();
    setError(""); setBusy(true);
    try { await login(password); } catch (reason) { setError(reason.message); } finally { setBusy(false); }
  }

  return <main className="login-page">
    <section className="login-panel">
      <div className="login-brand"><span>CT</span><div><strong>Ítalo Vieira</strong><small>Portal da equipe</small></div></div>
      <div className="login-copy"><span className="eyebrow">ACESSO INTERNO</span><h1>Cada atendimento.<br />Um cuidado contínuo.</h1><p>Registre o dia, acompanhe as orientações e dê continuidade ao cuidado com cada aluno.</p></div>
    </section>
    <section className="login-form-wrap"><form className="login-form" onSubmit={submit}>
      <div className="icon-box"><LockKeyhole /></div><h2>Acessar portal</h2><p>Use a senha administrativa ou individual do professor.</p>
      {location.state?.message && <div className="notice">{location.state.message}</div>}
      {error && <div className="notice error">{error}</div>}
      <label>Senha<input autoFocus type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Digite sua senha" /></label>
      <button className="button primary large" disabled={busy || !password}>{busy ? "Entrando…" : "Entrar"}</button>
      <>{demo && <div className="notice"><strong>Prévia local · dados fictícios</strong><p>Professor: ProfessorDemo2026<br/>Gerente: GerenteDemo2026</p></div>}</><small className="security-note">Acesso protegido e restrito à equipe.</small>
    </form></section>
  </main>;
}
