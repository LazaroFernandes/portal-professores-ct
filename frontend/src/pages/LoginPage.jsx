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

  return <section className="portal-login" aria-labelledby="login-title">
    <h1 id="login-title">CT Professores</h1>
    <p>Registro diário e acompanhamento dos alunos.</p>
    <h2>Entrar</h2>
    <form onSubmit={submit}>
      {location.state?.message && <div role="status" className="notice">{location.state.message}</div>}
      <label>Senha<input name="password" type="password" autoComplete="current-password" required
        value={password} onChange={event => setPassword(event.target.value)} /></label>
      {error && <div className="notice error" role="alert">{error}</div>}
      <button className="button primary" disabled={busy}>{busy ? "Entrando…" : "Entrar"}</button>
    </form>
    {demo && <div className="notice"><strong>Prévia local · dados fictícios</strong><p>Professor: ProfessorDemo2026<br/>Gerente: GerenteDemo2026</p></div>}
  </section>;
}
