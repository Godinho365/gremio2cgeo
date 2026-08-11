import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "./AuthContext";
import { hasAnyRole, homePath } from "./roles";

/** Guarda de rota por perfil. Quem não tem o papel volta para a sua tela inicial. */
export default function RequireRole({ roles }: { roles: string[] }) {
  const { user } = useAuth();
  if (!hasAnyRole(user, roles)) return <Navigate to={homePath(user)} replace />;
  return <Outlet />;
}
