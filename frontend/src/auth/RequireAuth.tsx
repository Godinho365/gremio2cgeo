import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "./AuthContext";

export default function RequireAuth() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="page page-center">
        <div className="container-tight py-4 text-center text-secondary">Carregando…</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}
