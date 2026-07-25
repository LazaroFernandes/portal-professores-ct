import { LockKeyhole } from "lucide-react";
import { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { session, login } = useAuth();
  const location = useLocation();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (session?.role === "admin") return <Navigate to={location.state?.from || "/vencimentos"} replace />;

  async function submit(event) {
    event.preventDefault();
    setError(""); setBusy(true);
    try { await login(password); } catch (reason) { setError(reason.message); } finally { setBusy(false); }
  }

  return <main className="login-page">
    <section className="login-panel">
      <div className="login-brand"><span>CT</span><div><strong>Ítalo Vieira</strong><small>Vencimento dos planos</small></div></div>
      <div className="login-copy"><span className="eyebrow">ACESSO INTERNO</span><h1>Planos e pagamentos.<br />Informação direta.</h1><p>Acompanhe quem está em dia e quem ultrapassou o período de tolerância.</p></div>
    </section>
    <section className="login-form-wrap"><form className="login-form" onSubmit={submit}>
      <div className="icon-box"><LockKeyhole /></div><h2>Acessar portal</h2><p>Use a senha administrativa ou individual do professor.</p>
      {location.state?.message && <div className="notice">{location.state.message}</div>}
      {error && <div className="notice error">{error}</div>}
      <label>Senha<input autoFocus type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Digite sua senha" /></label>
      <button className="button primary large" disabled={busy || !password}>{busy ? "Entrando…" : "Entrar"}</button>
      <small className="security-note">Acesso protegido e restrito à equipe.</small>
    </form></section>
  </main>;
}
