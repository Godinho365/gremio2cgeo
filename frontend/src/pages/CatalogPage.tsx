import { IconPhoto, IconSearch } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import Pagination from "../components/Pagination";
import { type Asset, STATUS_META, useAssets, useCategories } from "../features/assets/api";

/**
 * Situação no catálogo, do mais forte para o mais fraco. Reserva aprovada que
 * já começou conta como cautelado — o bem está com a pessoa; a que ainda vai
 * começar aparece como reservado.
 */
function catalogStatus(asset: Asset): { label: string; cls: string } {
  if (asset.has_open_custody || asset.is_reserved_now) {
    return { label: "Cautelado", cls: "bg-red-lt" };
  }
  if (asset.has_upcoming_booking) return { label: "Reservado", cls: "bg-yellow-lt" };
  if (asset.status === "available") return { label: "Disponível", cls: "bg-green-lt" };
  return STATUS_META[asset.status] ?? { label: asset.status, cls: "bg-secondary-lt" };
}

/** 12 fecha três fileiras cheias na grade de quatro colunas. */
const POR_PAGINA = 12;

function CardSkeleton() {
  return (
    <div className="col-6 col-md-4 col-xl-3">
      <div className="card">
        <div className="ratio ratio-4x3 bg-secondary-lt placeholder-glow">
          <span className="placeholder w-100 h-100" />
        </div>
        <div className="card-body placeholder-glow">
          <div className="placeholder col-9 mb-2" />
          <div className="placeholder col-5" />
        </div>
      </div>
    </div>
  );
}

export default function CatalogPage() {
  const navigate = useNavigate();
  const categories = useCategories();
  const [category, setCategory] = useState("");
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  // Busca com debounce (350ms) — mesmo padrão da página de cautelas.
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
    page,
    pageSize: POR_PAGINA,
  });
  const items = data?.results ?? [];
  const count = data?.count ?? 0;

  return (
    <>
      <div className="page-header d-print-none">
        <div className="row align-items-center">
          <div className="col">
            <div className="page-pretitle">Bens do grêmio</div>
            <h2 className="page-title">Catálogo</h2>
          </div>
        </div>
      </div>

      <div className="card mt-3">
        <div className="card-body">
          <div className="input-icon mb-3">
            <span className="input-icon-addon">
              <IconSearch size={16} />
            </span>
            <input
              className="form-control"
              placeholder="Buscar pelo nome ou número de patrimônio…"
              value={qInput}
              onChange={(e) => setQInput(e.target.value)}
              autoFocus
            />
          </div>
          <div className="d-flex flex-wrap gap-2">
            <button
              type="button"
              className={`btn btn-sm ${category === "" ? "btn-primary" : "btn-outline-secondary"}`}
              onClick={() => {
                setCategory("");
                setPage(1);
              }}
            >
              Todas
            </button>
            {categories.data?.map((c) => (
              <button
                key={c.id}
                type="button"
                className={`btn btn-sm ${category === c.id ? "btn-primary" : "btn-outline-secondary"}`}
                onClick={() => {
                  setCategory((cur) => (cur === c.id ? "" : c.id));
                  setPage(1);
                }}
              >
                {c.name}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="row row-cards mt-1">
        {isLoading && [0, 1, 2, 3].map((i) => <CardSkeleton key={i} />)}

        {!isLoading && items.length === 0 && (
          <div className="col-12">
            <div className="card">
              <div className="card-body text-center text-secondary py-5">
                {q || category
                  ? "Nenhum bem encontrado para esse filtro."
                  : "Nenhum bem cadastrado ainda."}
              </div>
            </div>
          </div>
        )}

        {items.map((a) => {
          const status = catalogStatus(a);
          return (
            <div className="col-6 col-md-4 col-xl-3" key={a.id}>
              <div
                role="button"
                tabIndex={0}
                className="card card-link h-100"
                title={`Ver agenda de ${a.name}`}
                onClick={() => navigate(`/agenda?asset=${a.id}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") navigate(`/agenda?asset=${a.id}`);
                }}
              >
                <div className="ratio ratio-4x3 bg-secondary-lt rounded-top overflow-hidden">
                  {a.photo_data ? (
                    <img
                      src={a.photo_data}
                      alt={a.name}
                      style={{ objectFit: "cover", width: "100%", height: "100%" }}
                    />
                  ) : (
                    <span className="d-flex align-items-center justify-content-center text-secondary">
                      <IconPhoto size={36} />
                    </span>
                  )}
                </div>
                <div className="card-body d-flex flex-column">
                  <div className="fw-medium text-truncate" title={a.name}>
                    {a.name}
                  </div>
                  <div className="asset-tag">{a.asset_tag}</div>
                  <div className="mt-2 d-flex flex-wrap gap-1">
                    <span className={`badge ${status.cls}`}>{status.label}</span>
                    {a.category_name && (
                      <span className="badge bg-secondary-lt">{a.category_name}</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {count > 0 && (
        <div className="card mt-3">
          <Pagination
            page={page}
            count={count}
            label={{ one: "bem", many: "bens" }}
            pageSize={POR_PAGINA}
            loading={isFetching && !isLoading}
            onChange={(p) => {
              setPage(p);
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          />
        </div>
      )}
    </>
  );
}
