import { useState } from "react";

import { CONDITIONS } from "../features/assets/api";
import { type Custody, OUTCOMES, type ReturnCustody, useReturnCustody } from "../features/custody/api";

/** Devolução do bem cautelado: condição de entrada, resultado da inspeção e descrição. */
export default function ReturnCustodyModal({
  custody,
  onClose,
}: {
  custody: Custody;
  onClose: () => void;
}) {
  const ret = useReturnCustody();
  const [condition, setCondition] = useState("good");
  const [outcome, setOutcome] = useState<ReturnCustody["outcome"]>("ok");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await ret.mutateAsync({ id: custody.id, condition_in: condition, outcome, notes });
      onClose();
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response?.data
        ?.error?.message;
      setError(msg ?? "Não foi possível registrar a entrega.");
    }
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Entrega do bem — {custody.asset_name}</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                {error && <div className="alert alert-danger">{error}</div>}
                <div className="mb-3">
                  <label className="form-label">Responsável</label>
                  <input className="form-control" value={custody.holder_name} disabled />
                </div>
                <div className="mb-3">
                  <label className="form-label">Condição do item na entrega</label>
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
                  <label className="form-label">Descrição</label>
                  <textarea
                    className="form-control"
                    rows={2}
                    placeholder="Observações sobre o estado do bem…"
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
                  {ret.isPending ? "Registrando…" : "Registrar entrega"}
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
