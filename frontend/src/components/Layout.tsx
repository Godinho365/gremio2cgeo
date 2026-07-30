import {
  IconBox,
  IconCalendarEvent,
  IconClipboardCheck,
  IconFileText,
  IconLayoutDashboard,
  IconLogout,
  IconSettings,
  IconUsers,
} from "@tabler/icons-react";
import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

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
  { to: "/cautelas", label: "Cautelas", icon: IconFileText, end: false },
  { to: "/inventario", label: "Inventário", icon: IconClipboardCheck, end: false },
  { to: "/cadastros", label: "Cadastros", icon: IconSettings, end: false, roles: ["admin", "director"] },
  { to: "/usuarios", label: "Usuários", icon: IconUsers, end: false, roles: ["admin"] },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const roles = user?.roles ?? [];
  const items = NAV.filter((n) => !n.roles || n.roles.some((r) => roles.includes(r)));

  return (
    <div className="page">
      <aside className="navbar navbar-vertical navbar-expand-lg" data-bs-theme="dark">
        <div className="container-fluid">
          <h1 className="navbar-brand navbar-brand-autodark">
            <span className="fw-bold">Patrimonia</span>
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
            <div className="d-flex align-items-center gap-2">
              <span className="text-secondary d-none d-sm-inline">
                {user?.display_name ?? user?.username}
              </span>
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
            <Outlet />
          </div>
        </div>
      </div>
    </div>
  );
}
