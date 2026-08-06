import {
  IconAlertTriangle,
  IconArrowBackUp,
  IconChevronLeft,
  IconChevronRight,
  IconClipboardCheck,
  IconClock,
  IconPlus,
  IconSearch,
} from "@tabler/icons-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import IssueCustodyModal from "../components/IssueCustodyModal";
import { CONDITIONS } from "../features/assets/api";
import {
  CUSTODY_STATUS,
  type Custody,
  type CustodyStats,
  OUTCOMES,
  type ReturnCustody,
  useApproveCustody,
  useCustodies,
  useCustodyStats,
  useDeleteCustody,
  useRejectCustody,
  useReturnCustody,
} from "../features/custody/api";

const PAGE_SIZE = 25; // igual ao backend (REST_FRAMEWORK PAGE_SIZE)

function fmt(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR");
}

// Cards de estatística (clicáveis → filtram por situação).
const STAT_CARDS: {
  key: keyof CustodyStats;
  status: Custody["status"];
  label: string;
  color: string;
  icon: typeof IconClock;
}[] = [
  { key: "pending", status: "pending", label: "Solicitadas", color: "#f59f00", icon: IconClock },
  { key: "active", status: "active", label: "Ativas", color: "#2fb344", icon: IconClipboardCheck },
  { key: "overdue", status: "overdue", label: "Atrasadas", color: "#d63939", icon: IconAlertTriangle },
  {
    key: "returned",
    status: "returned",
    label: "Devolvidas",
    color: "#868e96",
    icon: IconArrowBackUp,
  },
];

function ReturnModal({ custody, onClose }: { custody: Custody; onClose: () => void }) {
  const ret = useReturnCustody();
  const [condition, setCondition] = useState("good");
  const [outcome, setOutcome] = useState<ReturnCustody["outcome"]>("ok");
  const [notes, setNotes] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    await ret.mutateAsync({ id: custody.id, condition_in: condition, outcome, notes });
    onClose();
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Devolução e inspeção — {custody.asset_name}</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                <div className="mb-3">
                  <label className="form-label">Estado na devolução</label>
                  <select
                    className="form-select"
                    value={condition}
                    onChange={(e) => setCondition(e.target.value)}
                  >
                    {CONDITIONS.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="mb-3">
                  <label className="form-label">Resultado da inspeção</label>
                  <select
                    className="form-select"
                    value={outcome}
                    onChange={(e) => setOutcome(e.target.value as ReturnCustody["outcome"])}
                  >
                    {OUTCOMES.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="mb-1">
                  <label className="form-label">Observações</label>
                  <textarea
                    className="form-control"
                    rows={2}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={ret.isPending}>
                  {ret.isPending ? "Registrando…" : "Registrar devolução"}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
      <div className="modal-backdrop fade show" />
    </>
  );
}

function StatCard({
  label,
  value,
  color,
  icon,
  active,
  loading,
  onClick,
}: {
  label: string;
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
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const from = count === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE, count);

  const hasFilter = !!status || !!q;

  function selectStatus(next: string) {
    setStatus((cur) => (cur === next ? "" : next)); // clicar de novo limpa
    setPage(1);
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
              Nova cautela
            </button>
          </div>
        </div>
      </div>

      {/* Estatísticas (clicáveis → filtram) */}
      <div className="row row-cards mt-1">
        {STAT_CARDS.map((c) => (
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
                  setPage(1);
                }}
              >
                <option value="">Todas as situações</option>
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
                <th>Solicitada</th>
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
                      : "Nenhuma cautela. Clique em “Nova cautela” para solicitar."}
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
                        <div className="text-secondary small">{c.asset_tag}</div>
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
                          {open && (
                            <button
                              className="btn btn-sm btn-primary"
                              onClick={() => setReturning(c)}
                            >
                              Devolver
                            </button>
                          )}
                          <button
                            className="btn btn-sm btn-ghost-danger"
                            onClick={() => {
                              if (confirm("Excluir esta cautela?")) del.mutate(c.id);
                            }}
                          >
                            Excluir
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="card-footer d-flex align-items-center">
          <p className="m-0 text-secondary">
            {count > 0 ? (
              <>
                Mostrando <strong>{from}</strong>–<strong>{to}</strong> de <strong>{count}</strong>
              </>
            ) : (
              "Sem registros"
            )}
            {isFetching && !isLoading && <span className="ms-2 spinner-border spinner-border-sm" />}
          </p>
          <div className="ms-auto d-flex align-items-center gap-2">
            <span className="text-secondary">
              Página {page} de {totalPages}
            </span>
            <button
              className="btn btn-sm btn-outline-secondary"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <IconChevronLeft size={16} />
            </button>
            <button
              className="btn btn-sm btn-outline-secondary"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              <IconChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>

      {returning && <ReturnModal custody={returning} onClose={() => setReturning(null)} />}
      {showNew && <IssueCustodyModal onClose={() => setShowNew(false)} />}
    </>
  );
}
