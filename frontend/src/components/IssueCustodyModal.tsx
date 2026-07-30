import { useState } from "react";

import { useUsers } from "../features/accounts/api";
import { CONDITIONS, useAssets } from "../features/assets/api";
import { useIssueCustody } from "../features/custody/api";

export default function IssueCustodyModal({
  asset: fixedAsset,
  assetLabel,
  defaultHolder,
  bookingId,
  onClose,
}: {
  asset?: string;
  assetLabel?: string;
  defaultHolder?: string;
  bookingId?: string | null;
  onClose: () => void;
}) {
  const users = useUsers();
  const assets = useAssets();
  const issue = useIssueCustody();
  const [asset, setAsset] = useState(fixedAsset ?? "");
  const [holder, setHolder] = useState(defaultHolder ?? "");
  const [due, setDue] = useState("");
  const [condition, setCondition] = useState("good");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
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
                      className="form-control"
                      value={due}
                      onChange={(e) => setDue(e.target.value)}
                      required
                    />
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
                <button type="submit" className="btn btn-primary" disabled={issue.isPending}>
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
