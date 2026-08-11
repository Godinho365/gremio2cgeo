import {
  IconBox,
  IconPhoto,
  IconPlus,
  IconPrinter,
  IconQrcode,
  IconSearch,
} from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import Pagination from "../components/Pagination";
import {
  type Asset,
  ASSET_STATUS,
  AssetInput,
  CONDITIONS,
  fetchAssetQrUrl,
  STATUS_META,
  useAssets,
  useAssetStats,
  useCategories,
  useCreateAsset,
  useDeleteAsset,
  useLocations,
  useUpdateAsset,
} from "../features/assets/api";
import { fileToResizedDataUrl } from "../lib/image";
import { LABELS_PER_SHEET, printLabelSheet } from "../lib/labels";

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
  const [photo, setPhoto] = useState(asset?.photo_data ?? "");
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof AssetInput, v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function onPhotoPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError(null);
    try {
      setPhoto(await fileToResizedDataUrl(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar a imagem.");
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const body: AssetInput = {
      name: form.name,
      category: form.category || null,
      location: form.location || null,
      condition: form.condition,
      description: form.description,
      photo_data: photo,
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
                <div className="mb-3">
                  <label className="form-label">Descrição</label>
                  <textarea
                    className="form-control"
                    rows={2}
                    value={form.description}
                    onChange={(e) => set("description", e.target.value)}
                  />
                </div>
                <div className="mb-1">
                  <label className="form-label">Foto (aparece no catálogo)</label>
                  <div className="d-flex align-items-start gap-3">
                    <div
                      className="rounded border bg-secondary-lt d-flex align-items-center justify-content-center flex-shrink-0 overflow-hidden"
                      style={{ width: 96, height: 96 }}
                    >
                      {photo ? (
                        <img
                          src={photo}
                          alt="Prévia"
                          style={{ objectFit: "cover", width: "100%", height: "100%" }}
                        />
                      ) : (
                        <IconPhoto size={28} className="text-secondary" />
                      )}
                    </div>
                    <div className="flex-fill">
                      <input
                        type="file"
                        accept="image/*"
                        className="form-control"
                        onChange={onPhotoPick}
                      />
                      <small className="form-hint">
                        A imagem é reduzida automaticamente antes de salvar.
                      </small>
                      {photo && (
                        <button
                          type="button"
                          className="btn btn-sm btn-ghost-danger mt-2"
                          onClick={() => setPhoto("")}
                        >
                          Remover foto
                        </button>
                      )}
                    </div>
                  </div>
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
    const ok = printLabelSheet([{ asset_tag: asset.asset_tag, name: asset.name, qrUrl: url }]);
    if (!ok) alert("Permita pop-ups para imprimir a etiqueta.");
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
  // Filtros podem vir por link (ex.: a contagem de bens na tela de Cadastros).
  const [searchParams, setSearchParams] = useSearchParams();
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [category, setCategory] = useState(searchParams.get("category") ?? "");
  const [location, setLocation] = useState(searchParams.get("location") ?? "");
  const [status, setStatus] = useState(searchParams.get("status") ?? "");
  const [page, setPage] = useState(1);
  const [form, setForm] = useState<{ asset?: Asset } | null>(null);
  const [label, setLabel] = useState<Asset | null>(null);
  // Guarda o bem inteiro: a seleção sobrevive à troca de página.
  const [selected, setSelected] = useState<Map<string, Asset>>(new Map());
  const [printing, setPrinting] = useState(false);

  // Busca com debounce (350ms), como nas demais listagens.
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(qInput);
      setPage(1);
    }, 350);
    return () => clearTimeout(t);
  }, [qInput]);

  const { data, isLoading, isFetching } = useAssets({
    q: q || undefined,
    category: category || undefined,
    location: location || undefined,
    status: status || undefined,
    page,
  });
  const stats = useAssetStats();
  const categories = useCategories();
  const locations = useLocations();
  const update = useUpdateAsset();
  const del = useDeleteAsset();
  const [erro, setErro] = useState<string | null>(null);

  async function removeAsset(asset: Asset) {
    if (!confirm(`Excluir ${asset.asset_tag} — ${asset.name}?`)) return;
    setErro(null);
    try {
      await del.mutateAsync(asset.id);
      setSelected((prev) => {
        const next = new Map(prev);
        next.delete(asset.id);
        return next;
      });
    } catch (e) {
      const msg = (e as { response?: { data?: { error?: { message?: string } } } }).response?.data
        ?.error?.message;
      setErro(msg ?? "Não foi possível excluir o bem.");
    }
  }
  const isManager = user?.roles.some((r) => r === "admin" || r === "director") ?? false;
  const hasFilter = !!q || !!category || !!location || !!status;

  function changeFilter(setter: (v: string) => void, value: string) {
    setter(value);
    setPage(1);
    // A URL deixa de refletir o filtro assim que ele muda na mão.
    if (searchParams.size) setSearchParams({}, { replace: true });
  }

  const rows = data?.results ?? [];
  const count = data?.count ?? 0;

  // ── Seleção para etiquetas em folha (persiste ao trocar de página) ────────
  const allPageSelected = rows.length > 0 && rows.every((a) => selected.has(a.id));
  const selectedAssets = [...selected.values()];

  function toggleOne(asset: Asset) {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(asset.id)) next.delete(asset.id);
      else next.set(asset.id, asset);
      return next;
    });
  }

  function toggleAllOnPage() {
    setSelected((prev) => {
      const next = new Map(prev);
      if (allPageSelected) rows.forEach((a) => next.delete(a.id));
      else rows.forEach((a) => next.set(a.id, a));
      return next;
    });
  }

  async function printSelected() {
    // A seleção atravessa páginas; usa o que está em cache para montar a folha.
    const items = selectedAssets;
    if (items.length === 0) return;
    setPrinting(true);
    try {
      const qrs = await Promise.all(items.map((a) => fetchAssetQrUrl(a.id)));
      const ok = printLabelSheet(
        items.map((a, i) => ({ asset_tag: a.asset_tag, name: a.name, qrUrl: qrs[i] })),
      );
      if (!ok) alert("Permita pop-ups para imprimir as etiquetas.");
    } catch {
      alert("Não foi possível gerar as etiquetas. Tente novamente.");
    } finally {
      setPrinting(false);
    }
  }

  const selectedCount = selected.size;
  const sheets = Math.ceil(selectedCount / LABELS_PER_SHEET);

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
                  <div className="h1 mb-0 lh-1">{stats.data?.total ?? 0}</div>
                  <div className="text-secondary">Total de bens</div>
                </div>
              </div>
            </div>
          </div>
        </div>
        {(["available", "in_use", "maintenance"] as const).map((s) => (
          <div className="col-sm-6 col-lg-3" key={s}>
            <div className="card card-sm">
              <div className="card-body">
                <div className="h1 mb-0 lh-1">{stats.data?.[s] ?? 0}</div>
                <div className="text-secondary">{STATUS_META[s]?.label ?? s}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {erro && (
        <div className="alert alert-danger mt-3 d-flex align-items-center">
          <span className="flex-fill">{erro}</span>
          <button className="btn btn-sm btn-ghost-secondary" onClick={() => setErro(null)}>
            Fechar
          </button>
        </div>
      )}

      <div className="card mt-3">
        <div className="card-header">
          <div className="row w-100 g-2 align-items-center">
            <div className="col-12 col-lg">
              <div className="input-icon">
                <span className="input-icon-addon">
                  <IconSearch size={16} />
                </span>
                <input
                  className="form-control"
                  placeholder="Buscar por número ou nome…"
                  value={qInput}
                  onChange={(e) => setQInput(e.target.value)}
                />
              </div>
            </div>
            <div className="col-auto">
              <select
                className="form-select"
                value={category}
                onChange={(e) => changeFilter(setCategory, e.target.value)}
              >
                <option value="">Todos os tipos</option>
                {categories.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="col-auto">
              <select
                className="form-select"
                value={location}
                onChange={(e) => changeFilter(setLocation, e.target.value)}
              >
                <option value="">Todos os locais</option>
                {locations.data?.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="col-auto">
              <select
                className="form-select"
                value={status}
                onChange={(e) => changeFilter(setStatus, e.target.value)}
              >
                <option value="">Todas as situações</option>
                {ASSET_STATUS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            {hasFilter && (
              <div className="col-auto">
                <button
                  className="btn btn-link"
                  onClick={() => {
                    setQInput("");
                    setQ("");
                    setCategory("");
                    setLocation("");
                    setStatus("");
                    setPage(1);
                  }}
                >
                  Limpar
                </button>
              </div>
            )}
          </div>
        </div>

        {selectedCount > 0 && (
          <div className="card-body border-bottom bg-primary-lt py-2 d-flex align-items-center gap-2 flex-wrap">
            <span className="fw-medium">
              {selectedCount} {selectedCount === 1 ? "bem selecionado" : "bens selecionados"}
            </span>
            <span className="text-secondary small">
              {sheets} {sheets === 1 ? "folha" : "folhas"} · até {LABELS_PER_SHEET} etiquetas por
              folha
            </span>
            <div className="btn-list ms-auto">
              <button className="btn btn-sm btn-link" onClick={() => setSelected(new Map())}>
                Limpar seleção
              </button>
              <button className="btn btn-sm btn-primary" onClick={printSelected} disabled={printing}>
                <IconPrinter size={16} className="me-1" />
                {printing ? "Gerando…" : "Imprimir etiquetas"}
              </button>
            </div>
          </div>
        )}
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th className="w-1">
                  <input
                    type="checkbox"
                    className="form-check-input m-0 align-middle"
                    title="Selecionar os bens desta página"
                    checked={allPageSelected}
                    onChange={toggleAllOnPage}
                    disabled={rows.length === 0}
                  />
                </th>
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
                  <td colSpan={7} className="text-secondary">
                    Carregando…
                  </td>
                </tr>
              )}
              {!isLoading && rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-secondary text-center py-4">
                    {hasFilter ? "Nenhum bem para os filtros." : "Nenhum bem cadastrado ainda."}
                  </td>
                </tr>
              )}
              {rows.map((a) => (
                <tr key={a.id}>
                  <td>
                    <input
                      type="checkbox"
                      className="form-check-input m-0 align-middle"
                      title="Selecionar para etiqueta"
                      checked={selected.has(a.id)}
                      onChange={() => toggleOne(a)}
                    />
                  </td>
                  <td className="asset-tag">{a.asset_tag}</td>
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
                        <>
                          <button
                            className="btn btn-sm btn-ghost-secondary"
                            onClick={() => setForm({ asset: a })}
                          >
                            Editar
                          </button>
                          <button
                            className="btn btn-sm btn-ghost-danger"
                            onClick={() => removeAsset(a)}
                            disabled={del.isPending}
                          >
                            Excluir
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <Pagination
          page={page}
          count={count}
          label={{ one: "bem", many: "bens" }}
          loading={isFetching && !isLoading}
          onChange={setPage}
        />
      </div>

      {form && <AssetFormModal asset={form.asset} onClose={() => setForm(null)} />}
      {label && <LabelModal asset={label} onClose={() => setLabel(null)} />}
    </>
  );
}
