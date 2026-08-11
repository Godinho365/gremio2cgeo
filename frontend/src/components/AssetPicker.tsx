import { IconSearch } from "@tabler/icons-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { type Asset, STATUS_META } from "../features/assets/api";

// Cor da bolinha de status (mesma semântica dos badges do STATUS_META).
const STATUS_DOT: Record<string, string> = {
  available: "#2fb344",
  reserved: "#f59f00",
  in_use: "#206bc4",
  maintenance: "#f76707",
  written_off: "#868e96",
};

// Estado que sobrepõe o status do bem no seletor (cautela ou reserva).
// "Cautelado" (vermelho) = está com alguém HOJE (cautela ativa OU reserva cobrindo hoje).
// "Aprovada" (azul) = reserva futura (a pessoa ainda não começou).
export type AssetStateKind =
  | "custody_active" // cautela ativa (com o militar hoje)
  | "in_use" // reserva aprovada cujo período inclui hoje
  | "reserved" // reserva aprovada futura
  | "custody_pending"
  | "booking_pending";

export interface AssetStateInfo {
  holder: string; // militar (cautela) ou solicitante (reserva)
  kind: AssetStateKind;
}

export const STATE_META: Record<
  AssetStateKind,
  { badge: string; label: string; line: string; dot: string; text: string }
> = {
  custody_active: {
    badge: "bg-red-lt",
    label: "Cautelado",
    line: "Cautelado a",
    dot: "#d63939",
    text: "text-danger",
  },
  in_use: {
    badge: "bg-red-lt",
    label: "Cautelado",
    line: "Reservado por",
    dot: "#d63939",
    text: "text-danger",
  },
  reserved: {
    badge: "bg-blue-lt",
    label: "Aprovada",
    line: "Reservado por",
    dot: "#206bc4",
    text: "text-primary",
  },
  custody_pending: {
    badge: "bg-yellow-lt",
    label: "Solicitada",
    line: "Cautela solicitada ·",
    dot: "#f59f00",
    text: "text-warning",
  },
  booking_pending: {
    badge: "bg-yellow-lt",
    label: "Pendente",
    line: "Reserva pendente ·",
    dot: "#f59f00",
    text: "text-warning",
  },
};

function StatusBadge({ status }: { status: string }) {
  const meta = STATUS_META[status];
  return (
    <span className={`badge flex-shrink-0 ${meta?.cls ?? "bg-secondary-lt"}`}>
      {meta?.label ?? status}
    </span>
  );
}

function Dot({ color }: { color: string }) {
  return (
    <span
      className="flex-shrink-0"
      style={{ width: 9, height: 9, borderRadius: "50%", backgroundColor: color }}
    />
  );
}

export default function AssetPicker({
  assets,
  value,
  onChange,
  state = {},
  placeholder = "Selecione um bem…",
}: {
  assets: Asset[];
  value: string;
  onChange: (id: string) => void;
  /** assetId → estado (cautela/reserva) que sobrepõe o status no seletor. */
  state?: Record<string, AssetStateInfo>;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  const selected = assets.find((a) => a.id === value) ?? null;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return assets;
    return assets.filter(
      (a) =>
        a.name.toLowerCase().includes(q) || a.asset_tag.toLowerCase().includes(q),
    );
  }, [assets, query]);

  // Fecha ao clicar fora ou pressionar Esc.
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function pick(id: string) {
    onChange(id);
    setOpen(false);
    setQuery("");
  }

  const selState = selected ? state[selected.id] : undefined;
  const selMeta = selState ? STATE_META[selState.kind] : null;

  return (
    <div className="dropdown" ref={ref} style={{ minWidth: 280, position: "relative" }}>
      <button
        type="button"
        className="form-select text-start d-flex align-items-center gap-2"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        {selected ? (
          <>
            <Dot color={selMeta ? selMeta.dot : STATUS_DOT[selected.status] ?? "#868e96"} />
            <span className="flex-fill text-truncate" style={{ minWidth: 0 }}>
              <span className="fw-medium">{selected.asset_tag}</span>
              <span className="text-secondary"> — {selected.name}</span>
            </span>
            <span className="ps-2 text-nowrap flex-shrink-0">
              {selMeta && selState ? (
                <span className={`badge ${selMeta.badge}`}>
                  {selMeta.label} · {selState.holder}
                </span>
              ) : (
                <StatusBadge status={selected.status} />
              )}
            </span>
          </>
        ) : (
          <span className="text-secondary">{placeholder}</span>
        )}
      </button>

      {open && (
        <div
          className="dropdown-menu show p-0 mt-1 shadow"
          // Mais largo que o botão (alinhado à direita, cresce p/ esquerda) p/ o nome caber.
          style={{
            maxHeight: 340,
            overflowY: "auto",
            width: 440,
            minWidth: "100%",
            maxWidth: "90vw",
            right: 0,
            left: "auto",
          }}
        >
          <div className="p-2 border-bottom position-sticky top-0 bg-white" style={{ zIndex: 1 }}>
            <div className="input-icon">
              <span className="input-icon-addon">
                <IconSearch size={16} />
              </span>
              <input
                className="form-control form-control-sm"
                placeholder="Buscar bem…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                autoFocus
              />
            </div>
          </div>

          {filtered.length === 0 ? (
            <div className="dropdown-item text-secondary">Nenhum bem encontrado.</div>
          ) : (
            filtered.map((a) => {
              const info = state[a.id];
              const meta = info ? STATE_META[info.kind] : null;
              const isActive = a.id === value;
              return (
                <button
                  key={a.id}
                  type="button"
                  className={`dropdown-item d-flex align-items-center gap-2${
                    isActive ? " active" : ""
                  }`}
                  onClick={() => pick(a.id)}
                >
                  <Dot color={meta ? meta.dot : STATUS_DOT[a.status] ?? "#868e96"} />
                  <span className="flex-fill text-truncate" style={{ minWidth: 0 }}>
                    <span className="text-truncate d-block">
                      <span className="fw-medium">{a.asset_tag}</span>
                      <span className={isActive ? "" : "text-secondary"}> — {a.name}</span>
                    </span>
                    {meta && info && (
                      <span
                        className={`small d-block text-truncate ${isActive ? "" : meta.text}`}
                      >
                        {meta.line} {info.holder}
                      </span>
                    )}
                  </span>
                  {meta ? (
                    <span className={`badge flex-shrink-0 ${meta.badge}`}>{meta.label}</span>
                  ) : (
                    <StatusBadge status={a.status} />
                  )}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
