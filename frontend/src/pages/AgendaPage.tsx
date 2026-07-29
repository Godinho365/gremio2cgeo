import { IconPlus } from "@tabler/icons-react";
import { useState } from "react";

import { useAuth } from "../auth/AuthContext";
import { useAssets } from "../features/assets/api";
import {
  BOOKING_STATUS,
  useApproveBooking,
  useBookings,
  useCancelBooking,
  useCreateBooking,
} from "../features/scheduling/api";

function fmt(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function NewBookingModal({ onClose }: { onClose: () => void }) {
  const assets = useAssets();
  const create = useCreateBooking();
  const [asset, setAsset] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await create.mutateAsync({ asset, start_at: start, end_at: end });
      onClose();
    } catch (err) {
      const detail = (err as { response?: { data?: { error?: { message?: string } } } }).response
        ?.data?.error?.message;
      setError(detail ?? "Não foi possível criar a reserva.");
    }
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1} role="dialog">
        <div className="modal-dialog modal-dialog-centered" role="document">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Nova reserva</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                {error && <div className="alert alert-danger">{error}</div>}
                <div className="mb-3">
                  <label className="form-label required">Bem</label>
                  <select
                    className="form-select"
                    value={asset}
                    onChange={(e) => setAsset(e.target.value)}
                    required
                  >
                    <option value="">Selecione…</option>
                    {assets.data?.results.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.asset_tag} — {a.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="row">
                  <div className="col-md-6 mb-3">
                    <label className="form-label required">Início</label>
                    <input
                      type="datetime-local"
                      className="form-control"
                      value={start}
                      onChange={(e) => setStart(e.target.value)}
                      required
                    />
                  </div>
                  <div className="col-md-6 mb-3">
                    <label className="form-label required">Término</label>
                    <input
                      type="datetime-local"
                      className="form-control"
                      value={end}
                      onChange={(e) => setEnd(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={create.isPending}>
                  {create.isPending ? "Salvando…" : "Reservar"}
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

export default function AgendaPage() {
  const { user } = useAuth();
  const { data, isLoading } = useBookings();
  const approve = useApproveBooking();
  const cancel = useCancelBooking();
  const [showNew, setShowNew] = useState(false);

  const isManager = user?.roles.some((r) => r === "admin" || r === "director") ?? false;

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <h2 className="page-title">Agenda / Reservas</h2>
          </div>
          <div className="col-auto ms-auto">
            <button className="btn btn-primary" onClick={() => setShowNew(true)}>
              <IconPlus size={18} className="me-1" />
              Nova reserva
            </button>
          </div>
        </div>
      </div>

      <div className="card mt-3">
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th>Bem</th>
                <th>Solicitante</th>
                <th>Início</th>
                <th>Término</th>
                <th>Situação</th>
                <th className="w-1" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={6} className="text-secondary">
                    Carregando…
                  </td>
                </tr>
              )}
              {!isLoading && data?.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-secondary">
                    Nenhuma reserva ainda.
                  </td>
                </tr>
              )}
              {data?.results.map((b) => {
                const st = BOOKING_STATUS[b.status];
                const active = b.status === "pending" || b.status === "approved";
                return (
                  <tr key={b.id}>
                    <td>
                      <div>{b.asset_name}</div>
                      <div className="text-secondary small">{b.asset_tag}</div>
                    </td>
                    <td>{b.requester_name}</td>
                    <td>{fmt(b.start_at)}</td>
                    <td>{fmt(b.end_at)}</td>
                    <td>
                      <span className={`badge ${st.cls}`}>{st.label}</span>
                    </td>
                    <td>
                      <div className="btn-list flex-nowrap justify-content-end">
                        {isManager && b.status === "pending" && (
                          <button
                            className="btn btn-sm btn-success"
                            onClick={() => approve.mutate(b.id)}
                          >
                            Aprovar
                          </button>
                        )}
                        {active && (
                          <button
                            className="btn btn-sm btn-ghost-danger"
                            onClick={() => cancel.mutate(b.id)}
                          >
                            Cancelar
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {showNew && <NewBookingModal onClose={() => setShowNew(false)} />}
    </>
  );
}
