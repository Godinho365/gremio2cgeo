import { IconMap2, IconUpload, IconX } from "@tabler/icons-react";
import { useRef, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  type Asset,
  STATUS_META,
  useAssets,
  useFloorPlan,
  useSaveFloorPlan,
  useUpdateAsset,
} from "../features/assets/api";

// Cor do pino por situação do bem.
const STATUS_PIN: Record<string, string> = {
  available: "#2fb344",
  reserved: "#f59f00",
  in_use: "#206bc4",
  maintenance: "#f76707",
  written_off: "#868e96",
};

function pinColor(status: string) {
  return STATUS_PIN[status] ?? "#868e96";
}

export default function PlantaPage() {
  const { user } = useAuth();
  const isManager = user?.roles.some((r) => r === "admin" || r === "director") ?? false;

  const plan = useFloorPlan();
  const savePlan = useSaveFloorPlan();
  const assets = useAssets();
  const updateAsset = useUpdateAsset();

  const [placingId, setPlacingId] = useState<string | null>(null); // bem a posicionar
  const [active, setActive] = useState<Asset | null>(null); // pino clicado (info)
  const planRef = useRef<HTMLDivElement>(null);

  const list = assets.data?.results ?? [];
  const placed = list.filter((a) => a.plan_x != null && a.plan_y != null);
  const unplaced = list.filter((a) => a.plan_x == null || a.plan_y == null);

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 4 * 1024 * 1024) {
      alert("Imagem muito grande (máx. 4 MB). Reduza e tente de novo.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => savePlan.mutate({ id: plan.data?.id, image_data: reader.result as string });
    reader.readAsDataURL(f);
    e.target.value = "";
  }

  function onPlanClick(e: React.MouseEvent) {
    if (!isManager || !placingId || !planRef.current) return;
    const rect = planRef.current.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height));
    updateAsset.mutate({ id: placingId, plan_x: x, plan_y: y });
    setPlacingId(null);
  }

  function removeFromPlan(a: Asset) {
    updateAsset.mutate({ id: a.id, plan_x: null, plan_y: null });
    setActive(null);
  }

  return (
    <>
      <div className="page-header d-print-none">
        <div className="row align-items-center g-2">
          <div className="col">
            <div className="page-pretitle">Organização física</div>
            <h2 className="page-title">
              <IconMap2 className="icon me-2" />
              Planta da sala
            </h2>
          </div>
          {isManager && plan.data && (
            <div className="col-auto ms-auto">
              <label className="btn btn-outline-primary mb-0">
                <IconUpload size={18} className="me-1" />
                Trocar planta
                <input type="file" accept="image/*" hidden onChange={onFile} />
              </label>
            </div>
          )}
        </div>
      </div>

      {/* Sem planta ainda */}
      {!plan.isLoading && !plan.data && (
        <div className="card mt-3">
          <div className="card-body">
            <div className="empty">
              <div className="empty-icon">
                <IconMap2 size={48} className="text-secondary" />
              </div>
              <p className="empty-title">Nenhuma planta cadastrada</p>
              <p className="empty-subtitle text-secondary">
                {isManager
                  ? "Suba uma imagem da sala (foto ou desenho) para posicionar os bens sobre ela."
                  : "Peça a um gestor para cadastrar a planta da sala."}
              </p>
              {isManager && (
                <div className="empty-action">
                  <label className="btn btn-primary mb-0">
                    <IconUpload size={18} className="me-1" />
                    Enviar imagem da planta
                    <input type="file" accept="image/*" hidden onChange={onFile} />
                  </label>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {plan.data && (
        <div className="row row-cards mt-1">
          {/* Planta + pinos */}
          <div className="col-12 col-xl-9">
            <div className="card">
              <div className="card-header d-flex flex-wrap gap-3 align-items-center">
                {Object.entries(STATUS_META).map(([value, meta]) => (
                  <span key={value} className="d-inline-flex align-items-center">
                    <span
                      className="me-1"
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: "50%",
                        backgroundColor: pinColor(value),
                        display: "inline-block",
                      }}
                    />
                    <span className="text-secondary small">{meta.label}</span>
                  </span>
                ))}
                {placingId && (
                  <span className="ms-auto badge bg-blue-lt">
                    Clique na planta para posicionar
                  </span>
                )}
              </div>
              <div className="card-body p-2">
                <div
                  ref={planRef}
                  onClick={onPlanClick}
                  style={{
                    position: "relative",
                    width: "100%",
                    cursor: placingId ? "crosshair" : "default",
                    lineHeight: 0,
                  }}
                >
                  <img
                    src={plan.data.image_data}
                    alt="Planta da sala"
                    style={{ width: "100%", borderRadius: 8, display: "block" }}
                  />
                  {placed.map((a) => (
                    <button
                      key={a.id}
                      type="button"
                      title={`${a.asset_tag} — ${a.name}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setActive(a);
                      }}
                      style={{
                        position: "absolute",
                        left: `${(a.plan_x ?? 0) * 100}%`,
                        top: `${(a.plan_y ?? 0) * 100}%`,
                        transform: "translate(-50%, -50%)",
                        width: 22,
                        height: 22,
                        borderRadius: "50%",
                        border: "2px solid #fff",
                        boxShadow: "0 1px 4px rgba(0,0,0,.4)",
                        backgroundColor: pinColor(a.status),
                        cursor: "pointer",
                        padding: 0,
                      }}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Painel lateral: info do pino + bens a posicionar */}
          <div className="col-12 col-xl-3">
            {active && (
              <div className="card mb-3">
                <div className="card-status-top" style={{ backgroundColor: pinColor(active.status) }} />
                <div className="card-body">
                  <div className="d-flex align-items-start">
                    <div className="flex-fill">
                      <div className="fw-bold">{active.name}</div>
                      <div className="text-secondary small">{active.asset_tag}</div>
                      <span className={`badge mt-2 ${STATUS_META[active.status]?.cls ?? "bg-secondary-lt"}`}>
                        {STATUS_META[active.status]?.label ?? active.status}
                      </span>
                    </div>
                    <button className="btn btn-sm btn-ghost-secondary btn-icon" onClick={() => setActive(null)}>
                      <IconX size={16} />
                    </button>
                  </div>
                  {isManager && (
                    <div className="btn-list mt-3">
                      <button className="btn btn-sm btn-outline-primary" onClick={() => { setPlacingId(active.id); setActive(null); }}>
                        Mover
                      </button>
                      <button className="btn btn-sm btn-ghost-danger" onClick={() => removeFromPlan(active)}>
                        Remover da planta
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}

            {isManager && (
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">Posicionar bens</h3>
                </div>
                {unplaced.length === 0 ? (
                  <div className="card-body text-secondary">Todos os bens já estão na planta. 🎉</div>
                ) : (
                  <div className="list-group list-group-flush">
                    {unplaced.map((a) => (
                      <button
                        key={a.id}
                        type="button"
                        className={`list-group-item list-group-item-action d-flex align-items-center${
                          placingId === a.id ? " active" : ""
                        }`}
                        onClick={() => setPlacingId(a.id)}
                      >
                        <span
                          className="me-2 flex-shrink-0"
                          style={{
                            width: 10,
                            height: 10,
                            borderRadius: "50%",
                            backgroundColor: pinColor(a.status),
                          }}
                        />
                        <span className="flex-fill text-truncate">
                          <span className="fw-medium">{a.asset_tag}</span> — {a.name}
                        </span>
                        {placingId === a.id && <span className="small">clique na planta →</span>}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
