import {
  IconArrowRight,
  IconBuildingBank,
  IconBuildingWarehouse,
  IconLock,
  IconLogout,
  IconScissors,
} from "@tabler/icons-react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { hasAnyRole, isStaff } from "../auth/roles";
import { ORG_NAME } from "../branding";
import Brand from "../components/Brand";
import { useUsers } from "../features/accounts/api";
import { useAssetStats } from "../features/assets/api";
import { useAppointments } from "../features/barbershop/api";
import { useCustodyStats } from "../features/custody/api";
import { type ModuleId, MODULES } from "../modules";

const ICONS: Record<ModuleId, typeof IconBuildingBank> = {
  patrimonio: IconBuildingWarehouse,
  barbearia: IconScissors,
  autenticacao: IconLock,
  financeiro: IconBuildingBank,
};

/** Uma linha de números reais por módulo — nada inventado; some se não houver. */
function useModuleFacts(gestao: boolean, admin: boolean): Record<ModuleId, string[]> {
  // Cada consulta só sai quando o perfil tem acesso ao endpoint.
  const assets = useAssetStats({ enabled: gestao });
  const custody = useCustodyStats({ enabled: gestao });
  const users = useUsers({ enabled: admin });
  const meus = useAppointments({ scope: "mine", upcoming: true, pageSize: 1 });

  const bens = assets.data?.total;
  const fora = custody.data?.open;
  const pessoas = users.data?.length;
  const semAcesso = users.data?.filter((u) => !u.is_active).length;
  const marcados = meus.data?.count;

  return {
    patrimonio: [
      bens !== undefined ? `${bens} bens` : "",
      fora !== undefined ? `${fora} em poder de alguém` : "",
    ].filter(Boolean),
    barbearia: marcados ? [`${marcados} ${marcados === 1 ? "horário seu" : "horários seus"}`] : [],
    autenticacao: [
      pessoas !== undefined ? `${pessoas} cadastros` : "",
      semAcesso ? `${semAcesso} sem acesso` : "",
    ].filter(Boolean),
    financeiro: [],
  };
}

export default function ModulesPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const facts = useModuleFacts(isStaff(user), hasAnyRole(user, ["admin"]));
  const modules = MODULES.filter((m) => !m.roles || hasAnyRole(user, m.roles));

  return (
    <div className="modules-page">
      <div className="modules-shell">
        <header className="modules-head">
          <Brand iconOnly size="md" />
          <div className="lh-sm">
            <div className="modules-org">{ORG_NAME}</div>
            <div className="modules-user">
              {user?.display_name ? `Conectado como ${user.display_name}` : "Conectado"}
            </div>
          </div>
          <button className="btn btn-ghost-secondary btn-sm ms-auto" onClick={logout}>
            <IconLogout size={16} className="me-1" />
            Sair
          </button>
        </header>

        <h1 className="modules-title">Escolha o módulo</h1>

        <ul className="modules-list">
          {modules.map((m, i) => {
            const Icon = ICONS[m.id];
            const numero = String(i + 1).padStart(2, "0");
            return (
              <li key={m.id}>
                <button
                  type="button"
                  className="module-row"
                  disabled={!m.available}
                  onClick={() => navigate(m.to)}
                >
                  <span className="module-index">{numero}</span>
                  <span className="module-icon">
                    <Icon size={22} />
                  </span>
                  <span className="module-body">
                    <span className="module-name">{m.name}</span>
                    <span className="module-summary">{m.summary}</span>
                    {facts[m.id].length > 0 && (
                      <span className="module-facts">{facts[m.id].join(" · ")}</span>
                    )}
                  </span>
                  <span className="module-action">
                    {m.available ? (
                      <>
                        Entrar <IconArrowRight size={16} />
                      </>
                    ) : (
                      <span className="badge bg-secondary-lt">Em desenvolvimento</span>
                    )}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
