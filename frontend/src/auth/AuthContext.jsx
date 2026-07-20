import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api, setCsrfToken } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api("/api/auth/me")
      .then((data) => { setCsrfToken(data.csrf_token); setSession(data); })
      .catch(() => setSession(null))
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo(() => ({
    session,
    loading,
    async login(password) {
      const data = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ password }) });
      setCsrfToken(data.csrf_token);
      setSession(data);
      return data;
    },
    async logout() {
      await api("/api/auth/logout", { method: "POST" });
      setCsrfToken("");
      setSession(null);
    },
  }), [session, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
