import { Route, Routes } from "react-router-dom";

import RequireAuth from "./auth/RequireAuth";
import Layout from "./components/Layout";
import AgendaPage from "./pages/AgendaPage";
import AssetsPage from "./pages/AssetsPage";
import CadastrosPage from "./pages/CadastrosPage";
import CustodyPage from "./pages/CustodyPage";
import DashboardPage from "./pages/DashboardPage";
import InventoryDetailPage from "./pages/InventoryDetailPage";
import InventoryPage from "./pages/InventoryPage";
import LoginPage from "./pages/LoginPage";
import UsersPage from "./pages/UsersPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="patrimonio" element={<AssetsPage />} />
          <Route path="agenda" element={<AgendaPage />} />
          <Route path="cautelas" element={<CustodyPage />} />
          <Route path="cadastros" element={<CadastrosPage />} />
          <Route path="usuarios" element={<UsersPage />} />
          <Route path="inventario" element={<InventoryPage />} />
          <Route path="inventario/:id" element={<InventoryDetailPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
