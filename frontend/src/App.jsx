import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Loading } from "./components/AsyncState";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";

const AdminRetentionPage = lazy(() => import("./pages/AdminRetentionPage").then((module) => ({ default: module.AdminRetentionPage })));
const CrmPage = lazy(() => import("./pages/CrmPage").then((module) => ({ default: module.CrmPage })));
const MondayPage = lazy(() => import("./pages/MondayPage").then((module) => ({ default: module.MondayPage })));
const ProfessorPage = lazy(() => import("./pages/ProfessorPage").then((module) => ({ default: module.ProfessorPage })));
const TrainingPage = lazy(() => import("./pages/TrainingPage").then((module) => ({ default: module.TrainingPage })));

function Protected({ admin = false, children }) {
  const { session, loading } = useAuth(); const location = useLocation();
  if (loading) return <Loading label="Verificando acesso…" />;
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (admin && session.role !== "admin") return <Navigate to="/registro" replace />;
  return children;
}

export default function App() {
  const { session } = useAuth();
  return <Suspense fallback={<Loading label="Carregando modulo..." />}><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route element={<Protected><Layout /></Protected>}>
      <Route path="/registro" element={<ProfessorPage />} />
      <Route path="/admin/retencao" element={<Protected admin><AdminRetentionPage /></Protected>} />
      <Route path="/admin/segunda" element={<Protected admin><MondayPage /></Protected>} />
      <Route path="/admin/crm" element={<Protected admin><CrmPage /></Protected>} />
      <Route path="/admin/treinos" element={<Protected admin><TrainingPage /></Protected>} />
    </Route>
    <Route path="*" element={<Navigate to={session?.role === "admin" ? "/admin/retencao" : session ? "/registro" : "/login"} replace />} />
  </Routes></Suspense>;
}
