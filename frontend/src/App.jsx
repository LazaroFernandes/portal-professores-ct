import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Loading } from "./components/AsyncState";
import { LoginPage } from "./pages/LoginPage";

const FrequencyPage = lazy(() => import("./pages/FrequencyPage").then((module) => ({ default: module.FrequencyPage })));
const ProfessorPage = lazy(() => import("./pages/ProfessorPage").then((module) => ({ default: module.ProfessorPage })));
const ProfessorAnalysisPage = lazy(() => import("./pages/ProfessorAnalysisPage").then((module) => ({ default: module.ProfessorAnalysisPage })));

const PresencePage = lazy(() => import("./pages/PresencePage").then(m => ({ default: m.PresencePage })));
const PendingPresencePage = lazy(() => import("./pages/PendingPresencePage").then(m => ({ default: m.PendingPresencePage })));

function Protected({ children, roles }) {
  const { session, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading label="Verificando acesso..." />;
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (roles && !roles.includes(session.role)) return <Navigate to="/login" replace state={{ message: "Acesso nao autorizado." }} />;
  return children;
}

export default function App() {
  const { session } = useAuth();
  return <Suspense fallback={<Loading label="Carregando modulo..." />}><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/vencimentos" element={<Protected roles={["admin"]}><FrequencyPage /></Protected>} />
    <Route path="/admin/professores" element={<Protected roles={["admin"]}><ProfessorAnalysisPage /></Protected>} />
    <Route path="/academia" element={<Protected roles={["admin", "professor"]}><PresencePage /></Protected>} />
    <Route path="/pendencias" element={<Protected roles={["admin", "professor"]}><PendingPresencePage /></Protected>} />
    <Route path="/registro" element={<Protected roles={["admin", "professor"]}><ProfessorPage /></Protected>} />
    <Route path="/frequencia" element={<Navigate to="/vencimentos" replace />} />
    <Route path="*" element={<Navigate to={session?.role === "admin" ? "/vencimentos" : session?.role === "professor" ? "/registro" : "/login"} replace />} />
  </Routes></Suspense>;
}
