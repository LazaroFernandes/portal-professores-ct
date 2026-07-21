import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Loading } from "./components/AsyncState";
import { LoginPage } from "./pages/LoginPage";

const FrequencyPage = lazy(() => import("./pages/FrequencyPage").then((module) => ({ default: module.FrequencyPage })));

function Protected({ children }) {
  const { session, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading label="Verificando acesso…" />;
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (session.role !== "admin") return <Navigate to="/login" replace state={{ message: "Acesso administrativo necessário." }} />;
  return children;
}

export default function App() {
  const { session } = useAuth();
  return <Suspense fallback={<Loading label="Carregando módulo…" />}><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/vencimentos" element={<Protected><FrequencyPage /></Protected>} />
    <Route path="/frequencia" element={<Navigate to="/vencimentos" replace />} />
    <Route path="*" element={<Navigate to={session?.role === "admin" ? "/vencimentos" : "/login"} replace />} />
  </Routes></Suspense>;
}
