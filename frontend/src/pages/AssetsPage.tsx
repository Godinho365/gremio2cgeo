import { IconPlus, IconQrcode } from "@tabler/icons-react";
import { useEffect, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  type Asset,
  ASSET_STATUS,
  AssetInput,
  CONDITIONS,
  fetchAssetQrUrl,
  STATUS_META,
  useAssets,
  useCategories,
  useCreateAsset,
  useLocations,
  useUpdateAsset,
} from "../features/assets/api";

function AssetFormModal({ asset, onClose }: { asset?: Asset; onClose: () => void }) {
  const create = useCreateAsset();
  const update = useUpdateAsset();
  const categories = useCategories();
  const locations = useLocations();
  const editing = !!asset;
  const [form, setForm] = useState<AssetInput>({
    name: asset?.name ?? "",
    category: asset?.category ?? "",
    location: asset?.location ?? "",
    condition: asset?.condition ?? "good",
    status: asset?.status ?? "available",
    description: asset?.description ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof AssetInput, v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const body: AssetInput = {
      name: form.name,
      category: form.category || null,
      location: form.location || null,
      condition: form.condition,
      description: form.description,
    };
    try {
      if (editing) await update.mutateAsync({ id: asset.id, ...body, status: form.status });
      else await create.mutateAsync(body);
      onClose();
    } catch {
      setError("Não foi possível salvar o bem.");
    }
  }

  const pending = create.isPending || update.isPending;

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">
                {editing ? `Editar — ${asset.asset_tag}` : "Novo bem"}
              </h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                {error && <div className="alert alert-danger">{error}</div>}
                <div className="mb-3">
                  <label className="form-label required">Nome</label>
                  <input
                    className="form-control"
                    value={form.name}
                    onChange={(e) => set("name", e.target.value)}
                    autoFocus
                    required
                  />
                  {!editing && (
                    <small className="form-hint">A numeração (asset_tag) é gerada automaticamente.</small>
                  )}
                </div>
                <div className="row">
                  <div className="col-md-6 mb-3">
                    <label className="form-label">Categoria</label>
                    <select
                      className="form-select"
                      value={form.category ?? ""}
                      onChange={(e) => set("category", e.target.value)}
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
                      value={form.location ?? ""}
                      onChange={(e) => set("location", e.target.value)}
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
                <div className="row">
                  <div className="col-md-6 mb-3">
                    <label className="form-label">Estado de conservação</label>
                    <select
                      className="form-select"
                      value={form.condition}
                      onChange={(e) => set("condition", e.target.value)}
                    >
                      {CONDITIONS.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  {editing && (
                    <div className="col-md-6 mb-3">
                      <label className="form-label">Situação</label>
                      <select
                        className="form-select"
                        value={form.status}
                        onChange={(e) => set("status", e.target.value)}
                      >
                        {ASSET_STATUS.map((s) => (
                          <option key={s.value} value={s.value}>
                            {s.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
                <div className="mb-1">
                  <label className="form-label">Descrição</label>
                  <textarea
                    className="form-control"
                    rows={2}
                    value={form.description}
                    onChange={(e) => set("description", e.target.value)}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={pending}>
                  {pending ? "Salvando…" : editing ? "Salvar" : "Cadastrar"}
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

function LabelModal({ asset, onClose }: { asset: Asset; onClose: () => void }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    fetchAssetQrUrl(asset.id).then((u) => active && setUrl(u));
    return () => {
      active = false;
    };
  }, [asset.id]);

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered modal-sm">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Etiqueta patrimonial</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <div className="modal-body text-center">
              {url ? (
                <img src={url} alt="QR" style={{ width: 180, height: 180 }} />
              ) : (
                <div className="text-secondary py-5">Gerando QR…</div>
              )}
              <div className="mt-2 fw-bold">{asset.asset_tag}</div>
              <div className="text-secondary small">{asset.name}</div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-link" onClick={onClose}>
                Fechar
              </button>
              {url && (
                <a className="btn btn-primary" href={url} target="_blank" rel="noreferrer">
                  Abrir / Imprimir
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
      <div className="modal-backdrop fade show" />
    </>
  );
}

export default function AssetsPage() {
  const { user } = useAuth();
  const { data, isLoading } = useAssets();
  const update = useUpdateAsset();
  const [form, setForm] = useState<{ asset?: Asset } | null>(null);
  const [label, setLabel] = useState<Asset | null>(null);
  const isManager = user?.roles.some((r) => r === "admin" || r === "director") ?? false;

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <h2 className="page-title">Patrimônio</h2>
          </div>
          {isManager && (
            <div className="col-auto ms-auto">
              <button className="btn btn-primary" onClick={() => setForm({})}>
                <IconPlus size={18} className="me-1" />
                Novo bem
              </button>
            </div>
          )}
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
                    Nenhum bem cadastrado ainda.
                  </td>
                </tr>
              )}
              {data?.results.map((a) => (
                <tr key={a.id}>
                  <td className="text-secondary">{a.asset_tag}</td>
                  <td>{a.name}</td>
                  <td>{a.category_name ?? "—"}</td>
                  <td>{a.location_name ?? "—"}</td>
                  <td style={{ maxWidth: 160 }}>
                    {isManager ? (
                      <select
                        className="form-select form-select-sm"
                        value={a.status}
                        onChange={(e) => update.mutate({ id: a.id, status: e.target.value })}
                      >
                        {ASSET_STATUS.map((s) => (
                          <option key={s.value} value={s.value}>
                            {s.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className={`badge ${STATUS_META[a.status]?.cls ?? ""}`}>
                        {STATUS_META[a.status]?.label ?? a.status}
                      </span>
                    )}
                  </td>
                  <td>
                    <div className="btn-list flex-nowrap justify-content-end">
                      <button
                        className="btn btn-sm btn-icon btn-ghost-secondary"
                        title="Etiqueta / QR"
                        onClick={() => setLabel(a)}
                      >
                        <IconQrcode size={18} />
                      </button>
                      {isManager && (
                        <button
                          className="btn btn-sm btn-ghost-secondary"
                          onClick={() => setForm({ asset: a })}
                        >
                          Editar
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {form && <AssetFormModal asset={form.asset} onClose={() => setForm(null)} />}
      {label && <LabelModal asset={label} onClose={() => setLabel(null)} />}
    </>
  );
}
