import {
  IconAlertTriangle,
  IconArrowBackUp,
  IconCalendarEvent,
  IconClipboardCheck,
  IconClock,
  IconPackage,
  IconPlus,
  IconSearch,
} from "@tabler/icons-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import IssueCustodyModal from "../components/IssueCustodyModal";
import BookingsCard, { type BookingScope, isInCourse } from "../components/BookingsCard";
import Pagination from "../components/Pagination";
import ReturnCustodyModal from "../components/ReturnCustodyModal";
import {
  CUSTODY_STATUS,
  type Custody,
  type CustodyStats,
  useApproveCustody,
  useCustodies,
  useCustodyStats,
  useDeleteCustody,
  useRejectCustody,
} from "../features/custody/api";
import { useBookings } from "../features/scheduling/api";

function fmt(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR");
}

// Cards de estatística (clicáveis → filtram por situação).
type StatCardDef = {
  key: keyof CustodyStats;
  status: Custody["status"];
  label: string;
  color: string;
  icon: typeof IconClock;
};

// O gestor entrega direto; "Solicitadas" só existe quando um usuário comum pede
// um bem, então esse card só aparece se houver solicitação em aberto.
const STAT_CARDS: StatCardDef[] = [
  { key: "active", status: "active", label: "Entregues", color: "#2fb344", icon: IconClipboardCheck },
  { key: "overdue", status: "overdue", label: "Atrasadas", color: "#d63939", icon: IconAlertTriangle },
  {
    key: "returned",
    status: "returned",
    label: "Devolvidas",
    color: "#868e96",
    icon: IconArrowBackUp,
  },
];

const PENDING_CARD: StatCardDef = {
  key: "pending",
  status: "pending",
  label: "Solicitadas",
  color: "#f59f00",
  icon: IconClock,
};

function StatCard({
  label,
  hint,
  value,
  color,
  icon,
  active,
  loading,
  onClick,
}: {
  label: string;
  hint?: string;
  value: number | undefined;
  color: string;
  icon: React.ReactNode;
  active: boolean;
  loading: boolean;
  onClick: () => void;
}) {
  return (
    <div className="col-6 col-sm-3">
      <div
        role="button"
        onClick={onClick}
        className="card card-sm"
        style={{
          cursor: "pointer",
          borderColor: active ? color : undefined,
          borderWidth: active ? 2 : undefined,
        }}
      >
        <div className="card-body">
          <div className="row align-items-center">
            <div className="col-auto">
              <span className="avatar" style={{ backgroundColor: color, color: "#fff" }}>
                {icon}
              </span>
            </div>
            <div className="col">
              <div className="h1 mb-0 lh-1">
                {loading ? <span className="placeholder col-4" /> : (value ?? 0)}
              </div>
              <div className="text-secondary">{label}</div>
              {hint && <div className="text-secondary small">{hint}</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function CustodyPage() {
  const { user } = useAuth();
  const isManager = user?.roles.some((r) => r === "admin" || r === "director") ?? false;

  const [status, setStatus] = useState<string>("");
  // Recorte vindo dos cards de reserva ("Ativos" e "Reservados").
  const [scope, setScope] = useState<BookingScope>("all");
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  // Busca com debounce (350ms) para não requisitar a cada tecla.
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(qInput);
      setPage(1);
    }, 350);
    return () => clearTimeout(t);
  }, [qInput]);

  const stats = useCustodyStats();
  const { data, isLoading, isFetching } = useCustodies({
    status: status || undefined,
    q: q || undefined,
    page,
  });

  const approve = useApproveCustody();
  const reject = useRejectCustody();
  const del = useDeleteCustody();
  const [returning, setReturning] = useState<Custody | null>(null);
  const [showNew, setShowNew] = useState(false);

  const rows = data?.results ?? [];
  const count = data?.count ?? 0;

  const hasFilter = !!status || !!q || scope !== "all";
  // "Solicitadas" só entra na régua quando há pedido de usuário comum em aberto.
  const pendingCount = stats.data?.pending ?? 0;
  const cards = pendingCount > 0 ? [PENDING_CARD, ...STAT_CARDS] : STAT_CARDS;
  // Reservas aprovadas: as que já começaram contam como bem em uso (igual à agenda).
  const reserved = useBookings({ status: "approved", upcoming: true });
  const approvedRows = reserved.data?.results ?? [];
  const inCourseCount = approvedRows.filter(isInCourse).length;
  const reservedCount = approvedRows.length - inCourseCount;
  // "Ativos" = cautelas entregues + reservas já em curso.
  const activeCount = (stats.data?.active ?? 0) + (stats.data?.overdue ?? 0) + inCourseCount;

  function selectStatus(next: string) {
    setStatus((cur) => (cur === next ? "" : next)); // clicar de novo limpa
    setScope("all");
    setPage(1);
  }

  /** "Ativos" recorta as duas listas: reservas em curso + cautelas em aberto.
   *  "Reservados" só existe do lado das reservas. */
  function selectScope(next: Exclude<BookingScope, "all">) {
    const ligando = scope !== next;
    setScope(ligando ? next : "all");
    setStatus(ligando && next === "in-course" ? "open" : "");
    setPage(1);
    if (ligando) document.getElementById("reservas")?.scrollIntoView({ behavior: "smooth" });
  }

  const statusOptions = useMemo(
    () => Object.entries(CUSTODY_STATUS).map(([value, meta]) => ({ value, label: meta.label })),
    [],
  );

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <div className="page-pretitle">Termos de responsabilidade (Art. 30 d)</div>
            <h2 className="page-title">Cautelas</h2>
          </div>
          <div className="col-auto ms-auto">
            <button className="btn btn-primary" onClick={() => setShowNew(true)}>
              <IconPlus size={18} className="me-1" />
              Entregar bem
            </button>
          </div>
        </div>
      </div>

      {/* Reservas pendentes e reservadas — a cautela costuma nascer de uma reserva. */}
      <div className="row row-cards mt-1" id="reservas">
        <div className="col-12">
          <BookingsCard scope={scope} />
        </div>
      </div>

      {/* Situação geral: reservas em curso + cautelas (cards de cautela filtram a lista) */}
      <div className="row row-cards mt-1">
        <StatCard
          label="Ativos"
          hint="cautelas + reservas em curso"
          value={activeCount}
          color="var(--state-alert)"
          icon={<IconPackage size={22} />}
          active={scope === "in-course"}
          loading={stats.isLoading || reserved.isLoading}
          onClick={() => selectScope("in-course")}
        />
        <StatCard
          label="Reservados"
          hint="ainda vão começar"
          value={reservedCount}
          color="var(--hydro)"
          icon={<IconCalendarEvent size={22} />}
          active={scope === "upcoming"}
          loading={reserved.isLoading}
          onClick={() => selectScope("upcoming")}
        />
        {cards.map((c) => (
          <StatCard
            key={c.key}
            label={c.label}
            value={stats.data?.[c.key]}
            color={c.color}
            icon={<c.icon size={22} />}
            active={status === c.status}
            loading={stats.isLoading}
            onClick={() => selectStatus(c.status)}
          />
        ))}
      </div>

      <div className="card mt-3">
        <div className="card-header">
          <div className="row w-100 g-2 align-items-center">
            <div className="col">
              <div className="input-icon">
                <span className="input-icon-addon">
                  <IconSearch size={16} />
                </span>
                <input
                  className="form-control"
                  placeholder="Buscar por bem ou responsável…"
                  value={qInput}
                  onChange={(e) => setQInput(e.target.value)}
                />
              </div>
            </div>
            <div className="col-auto">
              <select
                className="form-select"
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setScope("all");
                  setPage(1);
                }}
              >
                <option value="">Todas as situações</option>
                <option value="open">Em aberto (ativa + atrasada)</option>
                {statusOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            {hasFilter && (
              <div className="col-auto">
                <button
                  className="btn btn-link"
                  onClick={() => {
                    setStatus("");
                    setScope("all");
                    setQInput("");
                    setQ("");
                    setPage(1);
                  }}
                >
                  Limpar
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th>Bem</th>
                <th>Responsável</th>
                <th>Entregue em</th>
                <th>Devolver até</th>
                <th>Situação</th>
                <th className="w-1" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={6} className="text-secondary text-center py-4">
                    Carregando…
                  </td>
                </tr>
              )}
              {!isLoading && rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-secondary text-center py-4">
                    {hasFilter
                      ? "Nenhuma cautela para os filtros aplicados."
                      : "Nenhuma cautela. Clique em “Entregar bem” para registrar uma."}
                  </td>
                </tr>
              )}
              {rows.map((c) => {
                const st = CUSTODY_STATUS[c.status];
                const open = c.status === "active" || c.status === "overdue";
                return (
                  <tr key={c.id}>
                    <td>
                      <Link
                        to={`/agenda?asset=${c.asset}`}
                        className="text-reset text-decoration-none"
                        title="Ver agenda deste bem"
                      >
                        <div className="fw-medium">{c.asset_name}</div>
                        <div className="asset-tag">{c.asset_tag}</div>
                      </Link>
                    </td>
                    <td>{c.holder_name}</td>
                    <td>{fmt(c.issued_at)}</td>
                    <td>{fmt(c.due_at)}</td>
                    <td>
                      <span className={`badge ${st.cls}`}>{st.label}</span>
                    </td>
                    <td>
                      {isManager && (
                        <div className="btn-list flex-nowrap justify-content-end">
                          {c.status === "pending" && (
                            <>
                              <button
                                className="btn btn-sm btn-success"
                                onClick={() => approve.mutate(c.id)}
                              >
                                Aprovar
                              </button>
                              <button
                                className="btn btn-sm btn-ghost-secondary"
                                onClick={() => reject.mutate(c.id)}
                              >
                                Rejeitar
                              </button>
                            </>
                          )}
                          {/* Cautela em curso: a única saída é registrar a entrega do bem. */}
                          {open ? (
                            <button
                              className="btn btn-sm btn-primary"
                              onClick={() => setReturning(c)}
                            >
                              Registrar entrega
                            </button>
                          ) : (
                            <button
                              className="btn btn-sm btn-ghost-danger"
                              onClick={() => {
                                if (confirm("Excluir esta cautela?")) del.mutate(c.id);
                              }}
                            >
                              Excluir
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <Pagination
          page={page}
          count={count}
          label={{ one: "cautela", many: "cautelas" }}
          loading={isFetching && !isLoading}
          onChange={setPage}
        />
      </div>

      {returning && <ReturnCustodyModal custody={returning} onClose={() => setReturning(null)} />}
      {showNew && <IssueCustodyModal onClose={() => setShowNew(false)} />}
    </>
  );
}
