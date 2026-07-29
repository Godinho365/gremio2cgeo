import { IconPlus } from "@tabler/icons-react";
import { useState } from "react";

import {
  CONDITIONS,
  useAssets,
  useCategories,
  useCreateAsset,
  useLocations,
} from "../features/assets/api";

const STATUS_LABEL: Record<string, string> = {
  available: "Disponível",
  reserved: "Reservado",
  in_use: "Em uso",
  maintenance: "Manutenção",
  written_off: "Baixado",
};

function NewAssetModal({ onClose }: { onClose: () => void }) {
  const create = useCreateAsset();
  const categories = useCategories();
  const locations = useLocations();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [condition, setCondition] = useState("good");
  const [category, setCategory] = useState("");
  const [location, setLocation] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await create.mutateAsync({
        name,
        description: description || undefined,
        condition,
        category: category || null,
        location: location || null,
      });
      onClose();
    } catch {
      setError("Não foi possível cadastrar o bem.");
    }
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
                {error && <div className="alert alert-danger">{error}</div>}
                <div className="mb-3">
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
                <div className="row">
                  <div className="col-md-6 mb-3">
                    <label className="form-label">Categoria</label>
                    <select
                      className="form-select"
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                    >
                      <option value="">—</option>
                      {categories.data?.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="col-md-6 mb-3">
                    <label className="form-label">Localização</label>
                    <select
                      className="form-select"
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                    >
                      <option value="">—</option>
                      {locations.data?.map((l) => (
                        <option key={l.id} value={l.id}>
                          {l.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="mb-3">
                  <label className="form-label">Estado de conservação</label>
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
                <div className="mb-1">
                  <label className="form-label">Descrição</label>
                  <textarea
                    className="form-control"
                    rows={2}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </div>
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
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <h2 className="page-title">Patrimônio</h2>
          </div>
          <div className="col-auto ms-auto">
            <button className="btn btn-primary" onClick={() => setShowNew(true)}>
              <IconPlus size={18} className="me-1" />
              Novo bem
            </button>
          </div>
        </div>
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
