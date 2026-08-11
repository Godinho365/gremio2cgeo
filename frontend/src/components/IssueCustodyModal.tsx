import { useState } from "react";

import { useUsers } from "../features/accounts/api";
import { CONDITIONS, useAssets } from "../features/assets/api";
import { useIssueCustody } from "../features/custody/api";
import { dateStr } from "../lib/dates";

/**
 * Entrega do bem: o gestor registra a quem entregou, quando, até quando e em
 * que estado. A cautela já nasce ativa — não há etapa de solicitação.
 */
export default function IssueCustodyModal({
  asset: fixedAsset,
  assetLabel,
  defaultHolder,
  defaultDue,
  /** Dia da entrega (ex.: o dia clicado na agenda). Padrão: hoje. */
  defaultIssued,
  bookingId,
  onClose,
}: {
  asset?: string;
  assetLabel?: string;
  defaultHolder?: string;
  defaultDue?: string;
  defaultIssued?: string;
  bookingId?: string | null;
  onClose: () => void;
}) {
  const users = useUsers();
  const assets = useAssets();
  const issue = useIssueCustody();
  const today = dateStr(new Date());
  const [asset, setAsset] = useState(fixedAsset ?? "");
  const [holder, setHolder] = useState(defaultHolder ?? "");
  // A entrega é de hoje para trás: não se entrega um bem no futuro.
  const [issued, setIssued] = useState(
    defaultIssued && defaultIssued <= today ? defaultIssued : today,
  );
  // Não pré-preenche com data passada (ex.: reserva antiga).
  const [due, setDue] = useState(defaultDue && defaultDue >= today ? defaultDue : "");
  const [condition, setCondition] = useState("good");
  const [error, setError] = useState<string | null>(null);

  const issuedFuture = issued > today;
  const dueBeforeIssued = due !== "" && due < issued;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (issuedFuture) {
      setError("A data da entrega não pode ser no futuro.");
      return;
    }
    if (dueBeforeIssued) {
      setError("A devolução não pode ser antes da entrega.");
      return;
    }
    try {
      await issue.mutateAsync({
        asset,
        holder,
        booking: bookingId ?? null,
        issued_at: `${issued}T12:00:00`,
        due_at: `${due}T23:59:00`,
        condition_out: condition,
      });
      onClose();
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response
        ?.data?.error?.message;
      setError(msg ?? "Não foi possível registrar a entrega.");
    }
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Entregar bem{assetLabel ? ` — ${assetLabel}` : ""}</h5>
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
                  <label className="form-label required">Entregue a</label>
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
                        {u.is_active ? "" : " (sem acesso)"}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="row">
                  <div className="col-6 mb-3">
                    <label className="form-label required">Data da entrega</label>
                    <input
                      type="date"
                      className={`form-control${issuedFuture ? " is-invalid" : ""}`}
                      value={issued}
                      max={today}
                      onChange={(e) => setIssued(e.target.value)}
                      required
                    />
                    {issuedFuture && (
                      <div className="invalid-feedback d-block">
                        A entrega não pode ser no futuro.
                      </div>
                    )}
                  </div>
                  <div className="col-6 mb-3">
                    <label className="form-label required">Devolver até</label>
                    <input
                      type="date"
                      className={`form-control${dueBeforeIssued ? " is-invalid" : ""}`}
                      value={due}
                      min={issued}
                      onChange={(e) => setDue(e.target.value)}
                      required
                    />
                    {dueBeforeIssued && (
                      <div className="invalid-feedback d-block">
                        Não pode ser antes da entrega.
                      </div>
                    )}
                  </div>
                </div>
                <div className="mb-1">
                  <label className="form-label">Estado do item na entrega</label>
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
                  <small className="form-hint">
                    Fica registrado para comparar com o estado na devolução.
                  </small>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={issue.isPending || issuedFuture || dueBeforeIssued}
                >
                  {issue.isPending ? "Entregando…" : "Entregar"}
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
