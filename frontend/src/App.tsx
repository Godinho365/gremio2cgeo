import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import RequireAuth from "./auth/RequireAuth";
import RequireRole from "./auth/RequireRole";
import {
  ADMIN_ROLES,
  BARBERSHOP_ROLES,
  MODULE_CHOOSER_ROLES,
  CADASTROS_ROLES,
  homePath,
  isStaff,
  STAFF_ROLES,
} from "./auth/roles";
import Layout from "./components/Layout";
import AgendaPage from "./pages/AgendaPage";
import AssetsPage from "./pages/AssetsPage";
import BarbershopAgendaPage from "./pages/BarbershopAgendaPage";
import BarbershopPage from "./pages/BarbershopPage";
import BarbersPage from "./pages/BarbersPage";
import CadastrosPage from "./pages/CadastrosPage";
import CatalogPage from "./pages/CatalogPage";
import CustodyPage from "./pages/CustodyPage";
import DashboardPage from "./pages/DashboardPage";
import FinancePage from "./pages/FinancePage";
import InventoryDetailPage from "./pages/InventoryDetailPage";
import InventoryPage from "./pages/InventoryPage";
import LoginPage from "./pages/LoginPage";
import ModulesPage from "./pages/ModulesPage";
import ProfilePage from "./pages/ProfilePage";
import SignupPage from "./pages/SignupPage";
import UsersPage from "./pages/UsersPage";

/** Tela inicial: dashboard para a gestão, catálogo para o usuário comum. */
function HomePage() {
  const { user } = useAuth();
  return isStaff(user) ? <DashboardPage /> : <Navigate to={homePath(user)} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route element={<RequireAuth />}>
        {/* Seleção de módulo fica fora do Layout: é a antessala de quem administra. */}
        <Route element={<RequireRole roles={MODULE_CHOOSER_ROLES} />}>
          <Route path="/modulos" element={<ModulesPage />} />
        </Route>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route element={<RequireRole roles={STAFF_ROLES} />}>
            <Route path="financeiro" element={<FinancePage />} />
          </Route>
          <Route path="perfil" element={<ProfilePage />} />
          <Route path="catalogo" element={<CatalogPage />} />
          <Route path="agenda" element={<AgendaPage />} />
          <Route path="barbearia" element={<BarbershopPage />} />
          <Route element={<RequireRole roles={BARBERSHOP_ROLES} />}>
            <Route path="barbearia/agenda" element={<BarbershopAgendaPage />} />
            <Route path="barbearia/barbeiros" element={<BarbersPage />} />
          </Route>
          <Route element={<RequireRole roles={STAFF_ROLES} />}>
            <Route path="patrimonio" element={<AssetsPage />} />
            <Route path="cautelas" element={<CustodyPage />} />
            <Route path="inventario" element={<InventoryPage />} />
            <Route path="inventario/:id" element={<InventoryDetailPage />} />
          </Route>
          <Route element={<RequireRole roles={CADASTROS_ROLES} />}>
            <Route path="cadastros" element={<CadastrosPage />} />
          </Route>
          <Route element={<RequireRole roles={ADMIN_ROLES} />}>
            <Route path="usuarios" element={<UsersPage />} />
          </Route>
        </Route>
      </Route>
      {/* Rota desconhecida (inclusive o antigo /signup) volta para o início. */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
