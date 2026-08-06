import {
  IconBox,
  IconBuildingWarehouse,
  IconCalendarEvent,
  IconClipboardCheck,
  IconFileText,
  IconLayoutDashboard,
  IconLogout,
  IconMap2,
  IconSettings,
  IconUsers,
} from "@tabler/icons-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import ErrorBoundary from "./ErrorBoundary";

type Nav = {
  to: string;
  label: string;
  icon: typeof IconBox;
  end: boolean;
  roles?: string[]; // se definido, só aparece para esses perfis
};

const NAV: Nav[] = [
  { to: "/", label: "Dashboard", icon: IconLayoutDashboard, end: true },
  { to: "/patrimonio", label: "Patrimônio", icon: IconBox, end: false },
  { to: "/agenda", label: "Agenda", icon: IconCalendarEvent, end: false },
  { to: "/planta", label: "Planta", icon: IconMap2, end: false },
  { to: "/cautelas", label: "Cautelas", icon: IconFileText, end: false },
  { to: "/inventario", label: "Inventário", icon: IconClipboardCheck, end: false },
  { to: "/cadastros", label: "Cadastros", icon: IconSettings, end: false, roles: ["admin", "director"] },
  { to: "/usuarios", label: "Usuários", icon: IconUsers, end: false, roles: ["admin"] },
];

const ROLE_LABEL: Record<string, string> = {
  admin: "Administrador",
  director: "Diretor",
  inventory: "Inventariante",
  user: "Usuário",
  auditor: "Auditor",
};

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const roles = user?.roles ?? [];
  const items = NAV.filter((n) => !n.roles || n.roles.some((r) => roles.includes(r)));

  const displayName = user?.display_name || user?.nome_guerra || user?.username || "";
  const initials = (user?.nome_guerra || user?.username || "?")
    .split(/\s+/)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  const roleLabel = roles.map((r) => ROLE_LABEL[r] ?? r).join(", ");

  return (
    <div className="page">
      <aside className="navbar navbar-vertical navbar-expand-lg" data-bs-theme="dark">
        <div className="container-fluid">
          <h1 className="navbar-brand navbar-brand-autodark">
            <span className="d-flex align-items-center gap-2">
              <IconBuildingWarehouse size={26} className="text-primary" />
              <span className="fw-bold">Patrimonia</span>
            </span>
          </h1>
          <div className="collapse navbar-collapse show">
            <ul className="navbar-nav pt-lg-3">
              {items.map(({ to, label, icon: Icon, end }) => (
                <li className="nav-item" key={to}>
                  <NavLink to={to} end={end} className="nav-link">
                    <span className="nav-link-icon">
                      <Icon size={20} />
                    </span>
                    <span className="nav-link-title">{label}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </aside>

      <header className="navbar navbar-expand-md d-print-none">
        <div className="container-xl">
          <div className="navbar-nav flex-row order-md-last">
            <div className="d-flex align-items-center gap-3">
              <div className="d-flex align-items-center gap-2">
                <span className="avatar avatar-sm bg-primary text-white">{initials}</span>
                <div className="d-none d-sm-block lh-sm">
                  <div className="fw-medium">{displayName}</div>
                  {roleLabel && <div className="text-secondary small">{roleLabel}</div>}
                </div>
              </div>
              <button className="btn btn-icon btn-ghost-secondary" onClick={logout} title="Sair">
                <IconLogout size={20} />
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="page-wrapper">
        <div className="page-body">
          <div className="container-xl">
            <ErrorBoundary key={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          </div>
        </div>
      </div>
    </div>
  );
}
