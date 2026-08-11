import {
  IconAlertTriangle,
  IconBox,
  IconClipboardCheck,
  IconClock,
  IconPackage,
} from "@tabler/icons-react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import BookingsCard, { isInCourse } from "../components/BookingsCard";
import { STATUS_META, useAssets } from "../features/assets/api";
import { CUSTODY_STATUS, useCustodies, useCustodyStats } from "../features/custody/api";
import { useBookings } from "../features/scheduling/api";

const STATUS_COLOR: Record<string, string> = {
  available: "#2fb344",
  reserved: "#f59f00",
  in_use: "#206bc4",
  maintenance: "#f76707",
  written_off: "#868e96",
};

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}

function StatCard({
  label,
  value,
  hint,
  color,
  icon,
  to,
}: {
  label: string;
  value: number | string;
  hint?: string;
  color: string;
  icon: React.ReactNode;
  to?: string;
}) {
  const body = (
    <div className="card card-sm h-100">
      <div className="card-body">
        <div className="row align-items-center">
          <div className="col-auto">
            <span className="avatar" style={{ backgroundColor: color, color: "#fff" }}>
              {icon}
            </span>
          </div>
          <div className="col">
            <div className="h1 mb-0 lh-1">{value}</div>
            <div className="text-secondary">{label}</div>
            {hint && <div className="text-secondary small mt-1">{hint}</div>}
          </div>
        </div>
      </div>
    </div>
  );
  return (
    <div className="col-sm-6 col-lg-3">
      {to ? (
        <Link to={to} className="text-reset text-decoration-none d-block h-100">
          {body}
        </Link>
      ) : (
        body
      )}
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const assets = useAssets();
  const stats = useCustodyStats();
  const bookings = useBookings({ status: "pending" });
  const aprovadas = useBookings({ status: "approved", upcoming: true });
  const recent = useCustodies();

  const totalAssets = assets.data?.count ?? 0;
  const assetRows = assets.data?.results ?? [];
  const dist = Object.keys(STATUS_META).map((s) => ({
    status: s,
    label: STATUS_META[s].label,
    color: STATUS_COLOR[s] ?? "#868e96",
    count: assetRows.filter((a) => a.status === s).length,
  }));
  const distTotal = assetRows.length || 1;

  const pendingBookings = bookings.data?.count ?? 0; // count do backend: não depende da paginação
  const overdue = stats.data?.overdue ?? 0;
  // Bem fora = cautela em aberto + reserva aprovada já em curso. É a mesma regra
  // do catálogo e da tela de cautelas; contar só cautela mostrava 0 com bens fora.
  const emCurso = (aprovadas.data?.results ?? []).filter(isInCourse).length;
  const fora = (stats.data?.open ?? 0) + emCurso;

  // A API já devolve por data de entrega decrescente: as três últimas.
  const recentList = (recent.data?.results ?? []).slice(0, 3);

  return (
    <>
      <div className="page-header d-print-none">
        <div className="row align-items-center">
          <div className="col">
            <div className="page-pretitle">Visão geral</div>
            <h2 className="page-title">
              {greeting()}, {user?.nome_guerra || user?.display_name || user?.username}
            </h2>
          </div>
          <div className="col-auto ms-auto text-secondary">
            {new Date().toLocaleDateString("pt-BR", {
              weekday: "long",
              day: "2-digit",
              month: "long",
              year: "numeric",
            })}
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="row row-cards mt-1">
        <StatCard
          label="Bens cadastrados"
          value={totalAssets}
          color="#206bc4"
          icon={<IconBox size={22} />}
          to="/patrimonio"
        />
        <StatCard
          label="Bens em poder de alguém"
          value={fora}
          hint="cautelas + reservas em curso"
          color="var(--state-alert)"
          icon={<IconClipboardCheck size={22} />}
          to="/cautelas"
        />
        <StatCard
          label="Cautelas atrasadas"
          value={overdue}
          color={overdue > 0 ? "#d63939" : "#868e96"}
          icon={<IconAlertTriangle size={22} />}
          to="/cautelas"
        />
        <StatCard
          label="Reservas pendentes"
          value={pendingBookings}
          color="#f59f00"
          icon={<IconClock size={22} />}
          to="/agenda"
        />
      </div>

      {/* Fila de reservas — o KPI acima só conta; aqui dá para agir. */}
      <div className="row row-cards mt-1">
        <div className="col-12">
          <BookingsCard perPage={3} />
        </div>
      </div>

      <div className="row row-cards mt-1">
        {/* Distribuição do patrimônio */}
        <div className="col-12 col-lg-5">
          <div className="card h-100">
            <div className="card-header">
              <h3 className="card-title">Situação do patrimônio</h3>
            </div>
            <div className="card-body">
              {assets.isLoading ? (
                <div className="text-secondary">Carregando…</div>
              ) : totalAssets === 0 ? (
                <div className="text-secondary">Nenhum bem cadastrado.</div>
              ) : (
                <>
                  <div className="progress progress-separated mb-3" style={{ height: 10 }}>
                    {dist
                      .filter((d) => d.count > 0)
                      .map((d) => (
                        <div
                          key={d.status}
                          className="progress-bar"
                          style={{ width: `${(d.count / distTotal) * 100}%`, backgroundColor: d.color }}
                          title={`${d.label}: ${d.count}`}
                        />
                      ))}
                  </div>
                  <div className="row g-2">
                    {dist.map((d) => (
                      <div key={d.status} className="col-6">
                        <div className="d-flex align-items-center">
                          <span
                            className="me-2"
                            style={{
                              width: 10,
                              height: 10,
                              borderRadius: 3,
                              backgroundColor: d.color,
                            }}
                          />
                          <span className="text-secondary">{d.label}</span>
                          <span className="ms-auto fw-medium">{d.count}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Atividade recente (cautelas) */}
        <div className="col-12 col-lg-7">
          <div className="card h-100">
            <div className="card-header">
              <h3 className="card-title">Cautelas recentes</h3>
              <div className="card-actions">
                <Link to="/cautelas" className="btn btn-sm btn-ghost-secondary">
                  Ver todas
                </Link>
              </div>
            </div>
            {recent.isLoading ? (
              <div className="card-body text-secondary">Carregando…</div>
            ) : recentList.length === 0 ? (
              <div className="card-body text-secondary text-center py-4">
                <IconPackage size={32} className="mb-2 d-block mx-auto opacity-50" />
                Nenhuma cautela registrada.
              </div>
            ) : (
              <div className="list-group list-group-flush">
                {recentList.map((c) => {
                  const st = CUSTODY_STATUS[c.status];
                  return (
                    <Link
                      key={c.id}
                      to={`/agenda?asset=${c.asset}`}
                      className="list-group-item list-group-item-action d-flex align-items-center"
                    >
                      <div className="flex-fill text-truncate">
                        <div className="text-truncate fw-medium">{c.asset_name}</div>
                        <div className="text-secondary small">{c.holder_name}</div>
                      </div>
                      <span className={`badge ${st.cls}`}>{st.label}</span>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
