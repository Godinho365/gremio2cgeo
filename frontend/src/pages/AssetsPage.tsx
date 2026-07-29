import { IconPlus } from "@tabler/icons-react";
import { useState } from "react";

import { useAssets, useCreateAsset } from "../features/assets/api";

const STATUS_LABEL: Record<string, string> = {
  available: "Disponível",
  reserved: "Reservado",
  in_use: "Em uso",
  maintenance: "Manutenção",
  written_off: "Baixado",
};

function NewAssetModal({ onClose }: { onClose: () => void }) {
  const create = useCreateAsset();
  const [name, setName] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    await create.mutateAsync({ name });
    onClose();
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1} role="dialog">
        <div className="modal-dialog modal-dialog-centered" role="document">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Novo bem</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                <label className="form-label required">Nome</label>
                <input
                  className="form-control"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoFocus
                  required
                />
                <small className="form-hint">
                  A numeração patrimonial (asset_tag) é gerada automaticamente.
                </small>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={create.isPending}>
                  {create.isPending ? "Salvando…" : "Cadastrar"}
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

export default function AssetsPage() {
  const { data, isLoading } = useAssets();
  const [showNew, setShowNew] = useState(false);

  return (
    <>
      <div className="page-header d-flex justify-content-between align-items-center">
        <h2 className="page-title">Patrimônio</h2>
        <button className="btn btn-primary" onClick={() => setShowNew(true)}>
          <IconPlus size={18} className="me-1" />
          Novo bem
        </button>
      </div>

      <div className="card mt-3">
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th>Numeração</th>
                <th>Nome</th>
                <th>Categoria</th>
                <th>Local</th>
                <th>Situação</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={5} className="text-secondary">
                    Carregando…
                  </td>
                </tr>
              )}
              {!isLoading && data?.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-secondary">
                    Nenhum bem cadastrado ainda.
                  </td>
                </tr>
              )}
              {data?.results.map((a) => (
                <tr key={a.id}>
                  <td>
                    <span className="text-secondary">{a.asset_tag}</span>
                  </td>
                  <td>{a.name}</td>
                  <td>{a.category_name ?? "—"}</td>
                  <td>{a.location_name ?? "—"}</td>
                  <td>
                    <span className="badge bg-blue-lt">
                      {STATUS_LABEL[a.status] ?? a.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showNew && <NewAssetModal onClose={() => setShowNew(false)} />}
    </>
  );
}
