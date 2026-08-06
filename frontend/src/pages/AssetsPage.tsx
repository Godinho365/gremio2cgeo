import { IconBox, IconPlus, IconPrinter, IconQrcode, IconSearch } from "@tabler/icons-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

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

  function printLabel() {
    if (!url) return;
    const esc = (s: string) =>
      s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
    const w = window.open("", "_blank", "width=420,height=460");
    if (!w) {
      alert("Permita pop-ups para imprimir a etiqueta.");
      return;
    }
    w.document.write(`<!doctype html><html><head><meta charset="utf-8">
      <title>Etiqueta ${esc(asset.asset_tag)}</title>
      <style>
        @page { margin: 8mm; }
        body { font-family: system-ui, Arial, sans-serif; margin: 0; }
        .label { display:inline-block; padding:14px 18px; border:2px solid #111; border-radius:10px; text-align:center; }
        .org { font-size:11px; letter-spacing:1px; text-transform:uppercase; color:#555; margin-bottom:6px; }
        img { width:180px; height:180px; }
        .tag { font-size:24px; font-weight:800; margin-top:8px; letter-spacing:1px; }
        .name { font-size:13px; color:#444; margin-top:2px; max-width:200px; }
        .wrap { text-align:center; padding:12px; }
      </style></head>
      <body><div class="wrap"><div class="label">
        <div class="org">Patrimônio</div>
        <img src="${url}" alt="QR"/>
        <div class="tag">${esc(asset.asset_tag)}</div>
        <div class="name">${esc(asset.name)}</div>
      </div></div>
      <script>window.onload=function(){window.focus();window.print();};</script>
      </body></html>`);
    w.document.close();
  }

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
              <button className="btn btn-primary" onClick={printLabel} disabled={!url}>
                <IconPrinter size={18} className="me-1" />
                Imprimir etiqueta
              </button>
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
  const [q, setQ] = useState("");
  const isManager = user?.roles.some((r) => r === "admin" || r === "director") ?? false;

  const all = data?.results ?? [];
  const filtered = useMemo(() => {
    const rows = data?.results ?? [];
    const term = q.trim().toLowerCase();
    if (!term) return rows;
    return rows.filter((a) =>
      [a.asset_tag, a.name, a.category_name, a.location_name]
        .filter(Boolean)
        .some((v) => v!.toLowerCase().includes(term)),
    );
  }, [data?.results, q]);

  const byStatus = (s: string) => all.filter((a) => a.status === s).length;

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <div className="page-pretitle">Bens da organização</div>
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

      <div className="row row-cards mt-1">
        <div className="col-sm-6 col-lg-3">
          <div className="card card-sm">
            <div className="card-body">
              <div className="row align-items-center">
                <div className="col-auto">
                  <span className="avatar bg-primary text-white">
                    <IconBox size={22} />
                  </span>
                </div>
                <div className="col">
                  <div className="h1 mb-0 lh-1">{data?.count ?? 0}</div>
                  <div className="text-secondary">Total de bens</div>
                </div>
              </div>
            </div>
          </div>
        </div>
        {["available", "in_use", "maintenance"].map((s) => (
          <div className="col-sm-6 col-lg-3" key={s}>
            <div className="card card-sm">
              <div className="card-body">
                <div className="h1 mb-0 lh-1">{byStatus(s)}</div>
                <div className="text-secondary">{STATUS_META[s]?.label ?? s}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="card mt-3">
        <div className="card-header">
          <div className="input-icon" style={{ maxWidth: 360 }}>
            <span className="input-icon-addon">
              <IconSearch size={16} />
            </span>
            <input
              className="form-control"
              placeholder="Buscar por número, nome, categoria…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <span className="ms-auto text-secondary small align-self-center">
            {filtered.length} {filtered.length === 1 ? "bem" : "bens"}
          </span>
        </div>
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
              {!isLoading && filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-secondary text-center py-4">
                    {q ? "Nenhum bem para a busca." : "Nenhum bem cadastrado ainda."}
                  </td>
                </tr>
              )}
              {filtered.map((a) => (
                <tr key={a.id}>
                  <td className="text-secondary">{a.asset_tag}</td>
                  <td>
                    <Link
                      to={`/agenda?asset=${a.id}`}
                      className="text-reset text-decoration-none fw-medium"
                      title="Ver agenda deste bem"
                    >
                      {a.name}
                    </Link>
                  </td>
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
