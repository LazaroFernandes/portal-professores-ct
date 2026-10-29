import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Loading } from "./components/AsyncState";
import { LoginPage } from "./pages/LoginPage";

const FrequencyPage = lazy(() => import("./pages/FrequencyPage").then((module) => ({ default: module.FrequencyPage })));
const FlowPage = lazy(() => import("./pages/FlowPage").then(m => ({default:m.FlowPage})));
const SchedulePage = lazy(() => import("./pages/SchedulePage").then((module) => ({ default: module.SchedulePage })));
const FinancePage = lazy(() => import("./pages/FinancePage").then((module) => ({ default: module.FinancePage })));
const ProfessorAnalysisPage = lazy(() => import("./pages/ProfessorAnalysisPage").then((module) => ({ default: module.ProfessorAnalysisPage })));

const DailyPage = lazy(() => import("./pages/DailyWorkflow").then(m => ({ default: m.DailyPage })));
const WeeklyHistoryPage = lazy(() => import("./pages/WeeklyHistoryPage").then(m => ({ default: m.WeeklyHistoryPage })));
const ActionsPage = lazy(() => import("./pages/DailyWorkflow").then(m => ({ default: m.ActionsPage })));

function Protected({ children, roles }) {
  const { session, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading label="Verificando acesso..." />;
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (roles && !roles.includes(session.role)) return <Navigate to="/academia" replace />;
  return children;
}

export default function App() {
  const { session } = useAuth();
  return <Suspense fallback={<Loading label="Carregando modulo..." />}><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/admin/fluxo" element={<Protected roles={["admin"]}><FlowPage /></Protected>} />
    <Route path="/admin/horarios" element={<Protected roles={["admin"]}><SchedulePage /></Protected>} />
    <Route path="/admin/financeiro" element={<Protected roles={["admin"]}><FinancePage /></Protected>} />
    <Route path="/vencimentos" element={<Protected roles={["admin"]}><FrequencyPage /></Protected>} />
    <Route path="/admin/professores" element={<Protected roles={["admin"]}><DailyPage analysis /></Protected>} />
    <Route path="/admin/historico-semanal" element={<Protected roles={["admin"]}><WeeklyHistoryPage /></Protected>} />
    <Route path="/admin/registros-semanais-antigos" element={<Protected roles={["admin"]}><ProfessorAnalysisPage /></Protected>} />
    <Route path="/acoes" element={<Protected roles={["admin", "professor"]}><ActionsPage /></Protected>} />
    <Route path="/academia" element={<Protected roles={["admin", "professor"]}><DailyPage /></Protected>} />
    <Route path="/pendencias" element={<Protected roles={["admin", "professor"]}><DailyPage pending /></Protected>} />
    <Route path="/registro" element={<Protected roles={["admin", "professor"]}><Navigate to="/academia" replace /></Protected>} />
    <Route path="/frequencia" element={<Navigate to="/vencimentos" replace />} />
    <Route path="*" element={<Navigate to={session?.role === "admin" ? "/admin/professores" : session?.role === "professor" ? "/academia" : "/login"} replace />} />
  </Routes></Suspense>;
}
