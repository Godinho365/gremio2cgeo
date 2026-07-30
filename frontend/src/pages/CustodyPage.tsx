import { useState } from "react";

import { useAuth } from "../auth/AuthContext";
import { CONDITIONS } from "../features/assets/api";
import {
  CUSTODY_STATUS,
  type Custody,
  OUTCOMES,
  type ReturnCustody,
  useCustodies,
  useReturnCustody,
} from "../features/custody/api";

function fmt(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR");
}

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

export default function CustodyPage() {
  const { user } = useAuth();
  const { data, isLoading } = useCustodies();
  const [returning, setReturning] = useState<Custody | null>(null);
  const isManager = user?.roles.some((r) => r === "admin" || r === "director") ?? false;

  return (
    <>
      <div className="page-header">
        <h2 className="page-title">Cautelas</h2>
      </div>

      <div className="card mt-3">
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th>Bem</th>
                <th>Responsável</th>
                <th>Emitida</th>
                <th>Devolver até</th>
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
                    Nenhuma cautela emitida. Emita a partir de uma reserva aprovada na Agenda.
                  </td>
                </tr>
              )}
              {data?.results.map((c) => {
                const st = CUSTODY_STATUS[c.status];
                const open = c.status === "active" || c.status === "overdue";
                return (
                  <tr key={c.id}>
                    <td>
                      <div>{c.asset_name}</div>
                      <div className="text-secondary small">{c.asset_tag}</div>
                    </td>
                    <td>{c.holder_name}</td>
                    <td>{fmt(c.issued_at)}</td>
                    <td>{fmt(c.due_at)}</td>
                    <td>
                      <span className={`badge ${st.cls}`}>{st.label}</span>
                    </td>
                    <td>
                      {isManager && open && (
                        <button
                          className="btn btn-sm btn-primary"
                          onClick={() => setReturning(c)}
                        >
                          Devolver
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {returning && <ReturnModal custody={returning} onClose={() => setReturning(null)} />}
    </>
  );
}
