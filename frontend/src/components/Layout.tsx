import {
  IconBox,
  IconBuildingBank,
  IconBuildingStore,
  IconCalendarEvent,
  IconChevronLeft,
  IconChevronRight,
  IconClipboardCheck,
  IconFileText,
  IconGridDots,
  IconLayoutDashboard,
  IconLogout,
  IconScissors,
  IconSettings,
  IconUserCircle,
  IconWallet,
  IconUsers,
} from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import {
  ADMIN_ROLES,
  BARBERSHOP_ROLES,
  CADASTROS_ROLES,
  canChooseModule,
  STAFF_ROLES,
} from "../auth/roles";
import { brandFor } from "../branding";
import { ROLE_LABEL } from "../features/accounts/api";
import { brl, useCredits } from "../features/barbershop/api";
import { type ModuleId, MODULES, moduleForPath } from "../modules";
import Brand from "./Brand";
import ErrorBoundary from "./ErrorBoundary";

type Nav = {
  to: string;
  label: string;
  icon: typeof IconBox;
  end: boolean;
  module: ModuleId;
  roles?: string[]; // se definido, só aparece para esses perfis
};

// Cada item pertence a um módulo; o rail mostra só os do módulo atual.
// O usuário comum enxerga catálogo e agenda; o resto é da gestão.
const NAV: Nav[] = [
  { to: "/", label: "Dashboard", icon: IconLayoutDashboard, end: true, module: "patrimonio", roles: STAFF_ROLES },
  { to: "/cadastros", label: "Cadastros", icon: IconSettings, end: false, module: "patrimonio", roles: CADASTROS_ROLES },
  { to: "/patrimonio", label: "Patrimônio", icon: IconBox, end: false, module: "patrimonio", roles: STAFF_ROLES },
  { to: "/catalogo", label: "Catálogo", icon: IconBuildingStore, end: false, module: "patrimonio" },
  { to: "/agenda", label: "Agenda", icon: IconCalendarEvent, end: false, module: "patrimonio" },
  { to: "/cautelas", label: "Cautelas", icon: IconFileText, end: false, module: "patrimonio", roles: STAFF_ROLES },
  { to: "/inventario", label: "Inventário", icon: IconClipboardCheck, end: false, module: "patrimonio", roles: STAFF_ROLES },
  { to: "/barbearia", label: "Barbearia", icon: IconScissors, end: true, module: "barbearia" },
  { to: "/barbearia/agenda", label: "Agenda do dia", icon: IconCalendarEvent, end: false, module: "barbearia", roles: BARBERSHOP_ROLES },
  { to: "/barbearia/barbeiros", label: "Barbeiros", icon: IconUsers, end: false, module: "barbearia", roles: BARBERSHOP_ROLES },
  { to: "/usuarios", label: "Usuários", icon: IconUsers, end: false, module: "autenticacao", roles: ADMIN_ROLES },
  { to: "/financeiro", label: "Financeiro", icon: IconBuildingBank, end: false, module: "financeiro", roles: STAFF_ROLES },
];

const RAIL_KEY = "rail-collapsed";

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const roles = user?.roles ?? [];
  const currentModule = moduleForPath(location.pathname);
  const escolheModulo = canChooseModule(user);
  const permitido = (n: Nav) => !n.roles || n.roles.some((r) => roles.includes(r));
  // Quem administra vê o menu do módulo atual; o usuário comum vê um menu só.
  const items = NAV.filter(
    (n) => permitido(n) && (!escolheModulo || n.module === currentModule),
  );
  const brand = brandFor(user);
  const moduleName = MODULES.find((m) => m.id === currentModule)?.name;

  // Rail recolhido: só os emblemas, com o rótulo no title. A escolha fica salva.
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(RAIL_KEY) === "1",
  );
  useEffect(() => {
    localStorage.setItem(RAIL_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  const displayName = user?.display_name || user?.nome_guerra || user?.username || "";
  const initials = (user?.nome_guerra || user?.username || "?")
    .split(/\s+/)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  const roleLabel = roles.map((r) => ROLE_LABEL[r] ?? r).join(", ");
  // Crédito de horário cancelado. Fica sempre à vista, mesmo zerado: assim a
  // pessoa sabe que o saldo é zero, em vez de ficar na dúvida se sumiu.
  const credito = useCredits();
  const saldo = Number(credito.data?.balance ?? 0);

  return (
    <div className={`page${collapsed ? " rail-collapsed" : ""}`}>
      <aside className="navbar navbar-vertical navbar-expand-lg">
        <div className="container-fluid">
          <h1 className="navbar-brand w-100">
            {collapsed ? (
              <Brand iconOnly plate className="mx-auto" />
            ) : (
              /* Para a gestão o rail anuncia o módulo em que ela está. */
              <Brand
                /* O rail anuncia o módulo só para quem navega entre módulos. */
                title={escolheModulo ? (moduleName ?? brand.title) : brand.title}
                subtitle={brand.subtitle}
                size="sm"
                className="w-100"
              />
            )}
          </h1>
          <div className="collapse navbar-collapse show">
            <ul className="navbar-nav pt-lg-3">
              {items.map(({ to, label, icon: Icon, end }) => (
                <li className="nav-item" key={to}>
                  <NavLink to={to} end={end} className="nav-link" title={label}>
                    <span className="nav-link-icon">
                      <Icon size={20} />
                    </span>
                    <span className="nav-link-title">{label}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
          <button
            type="button"
            className="rail-toggle"
            onClick={() => setCollapsed((c) => !c)}
            title={collapsed ? "Expandir menu" : "Recolher menu"}
            aria-label={collapsed ? "Expandir menu" : "Recolher menu"}
            aria-expanded={!collapsed}
          >
            {collapsed ? (
              <IconChevronRight size={16} />
            ) : (
              <>
                <IconChevronLeft size={16} />
                <span className="rail-toggle-text">Recolher</span>
              </>
            )}
          </button>
        </div>
      </aside>

      <header className="navbar navbar-expand-md d-print-none">
        {/* container-fluid + ms-auto: identidade do usuário colada na margem direita */}
        <div className="container-fluid">
          <div className="navbar-nav flex-row order-md-last ms-auto">
            <div className="d-flex align-items-center gap-3">
              {credito.isSuccess && (
                <NavLink
                  to="/perfil"
                  className={`credit-chip${saldo > 0 ? "" : " is-empty"}`}
                  title={
                    saldo > 0
                      ? "Seu crédito paga o próximo corte avulso. Clique para ver o extrato."
                      : "Você não tem crédito. Horário pago que for cancelado vira crédito aqui."
                  }
                >
                  <IconWallet size={16} />
                  <span>R$ {brl(saldo)}</span>
                </NavLink>
              )}
              {/* O acesso ao próprio cadastro fica aqui, ao lado do nome. */}
              <NavLink
                to="/perfil"
                className="d-flex align-items-center gap-2 text-reset text-decoration-none"
                title="Meu perfil"
              >
                <span className="avatar avatar-sm bg-primary text-white">{initials}</span>
                <div className="d-none d-sm-block lh-sm">
                  <div className="fw-medium d-flex align-items-center gap-1">
                    {displayName}
                    <IconUserCircle size={16} className="text-secondary" />
                  </div>
                  {roleLabel && <div className="text-secondary small">{roleLabel}</div>}
                </div>
              </NavLink>
              {escolheModulo && (
                <NavLink
                  to="/modulos"
                  className="btn btn-icon btn-ghost-secondary"
                  title="Trocar de módulo"
                >
                  <IconGridDots size={20} />
                </NavLink>
              )}
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
