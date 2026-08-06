import { useState } from "react";

import { useUsers } from "../features/accounts/api";
import { CONDITIONS, useAssets } from "../features/assets/api";
import { useIssueCustody } from "../features/custody/api";

// Data de hoje em "YYYY-MM-DD" (local) — piso para o prazo de devolução.
function todayStr(): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export default function IssueCustodyModal({
  asset: fixedAsset,
  assetLabel,
  defaultHolder,
  defaultDue,
  bookingId,
  onClose,
}: {
  asset?: string;
  assetLabel?: string;
  defaultHolder?: string;
  defaultDue?: string;
  bookingId?: string | null;
  onClose: () => void;
}) {
  const users = useUsers();
  const assets = useAssets();
  const issue = useIssueCustody();
  const today = todayStr();
  const [asset, setAsset] = useState(fixedAsset ?? "");
  const [holder, setHolder] = useState(defaultHolder ?? "");
  // Não pré-preenche com data passada (ex.: reserva antiga).
  const [due, setDue] = useState(defaultDue && defaultDue >= today ? defaultDue : "");
  const [condition, setCondition] = useState("good");
  const [error, setError] = useState<string | null>(null);

  const duePast = due !== "" && due < today; // prazo no passado → inválido

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (due < today) {
      setError("A data de devolução não pode ser no passado.");
      return;
    }
    try {
      await issue.mutateAsync({
        asset,
        holder,
        booking: bookingId ?? null,
        due_at: `${due}T23:59:00`,
        condition_out: condition,
      });
      onClose();
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response
        ?.data?.error?.message;
      setError(msg ?? "Não foi possível solicitar a cautela.");
    }
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">
                Solicitar cautela{assetLabel ? ` — ${assetLabel}` : ""}
              </h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                {error && <div className="alert alert-danger">{error}</div>}
                {!fixedAsset && (
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
                )}
                <div className="mb-3">
                  <label className="form-label required">Responsável</label>
                  <select
                    className="form-select"
                    value={holder}
                    onChange={(e) => setHolder(e.target.value)}
                    required
                  >
                    <option value="">Selecione…</option>
                    {users.data?.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.display_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="row">
                  <div className="col-6 mb-1">
                    <label className="form-label required">Devolver até</label>
                    <input
                      type="date"
                      className={`form-control${duePast ? " is-invalid" : ""}`}
                      value={due}
                      min={today}
                      onChange={(e) => setDue(e.target.value)}
                      required
                    />
                    {duePast && (
                      <div className="invalid-feedback d-block">
                        A data de devolução não pode ser no passado.
                      </div>
                    )}
                  </div>
                  <div className="col-6 mb-1">
                    <label className="form-label">Estado na entrega</label>
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
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={issue.isPending || duePast}
                >
                  {issue.isPending ? "Enviando…" : "Solicitar"}
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
