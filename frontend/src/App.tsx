import { Route, Routes } from "react-router-dom";

import RequireAuth from "./auth/RequireAuth";
import Layout from "./components/Layout";
import AgendaPage from "./pages/AgendaPage";
import AssetsPage from "./pages/AssetsPage";
import CustodyPage from "./pages/CustodyPage";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import PlaceholderPage from "./pages/PlaceholderPage";

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
          <Route path="inventario" element={<PlaceholderPage title="Inventário" />} />
        </Route>
      </Route>
    </Routes>
  );
}
