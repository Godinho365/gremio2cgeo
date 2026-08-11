import { IconUser } from "@tabler/icons-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import Pagination from "../components/Pagination";
import { CONDITIONS, useLocations } from "../features/assets/api";
import {
  DISCREPANCY_META,
  type InventoryItem,
  useCloseInventory,
  useInventories,
  useInventoryItems,
  useInventoryReport,
  useScanItem,
} from "../features/inventory/api";

/** Itens por página na conferência. */
const POR_PAGINA = 9;

function ScanModal({
  inventoryId,
  item,
  onClose,
}: {
  inventoryId: string;
  item: InventoryItem;
  onClose: () => void;
}) {
  const scan = useScanItem(inventoryId);
  const locations = useLocations();
  const [foundLocation, setFoundLocation] = useState(item.found_location ?? "");
  const [condition, setCondition] = useState(item.condition_found || "good");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    await scan.mutateAsync({
      item: item.id,
      found_location: foundLocation || null,
      condition_found: condition,
    });
    onClose();
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered modal-sm">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Conferir — {item.asset_name}</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                <div className="mb-2 text-secondary small">
                  Esperado em: {item.expected_location_name ?? "—"}
                </div>
                <div className="mb-3">
                  <label className="form-label">Encontrado em</label>
                  <select
                    className="form-select"
                    value={foundLocation}
                    onChange={(e) => setFoundLocation(e.target.value)}
                  >
                    <option value="">(local esperado)</option>
                    {locations.data?.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="mb-1">
                  <label className="form-label">Estado</label>
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
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-success" disabled={scan.isPending}>
                  Confirmar
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

function Stat({ label, value, cls }: { label: string; value: number; cls: string }) {
  return (
    <div className="col">
      <div className="card card-sm">
        <div className="card-body text-center">
          <div className={`h1 m-0 ${cls}`}>{value}</div>
          <div className="text-secondary">{label}</div>
        </div>
      </div>
    </div>
  );
}

export default function InventoryDetailPage() {
  const { id = "" } = useParams();
  const inventories = useInventories();
  const items = useInventoryItems(id);
  const report = useInventoryReport(id);
  const close = useCloseInventory(id);
  const [scanning, setScanning] = useState<InventoryItem | null>(null);
  const [pagina, setPagina] = useState(1);

  const inv = inventories.data?.results.find((i) => i.id === id);
  const isOpen = inv?.status === "open";

  // A conferência é longa: pagina de 9 em 9 sobre a lista já carregada.
  const todosItens = items.data ?? [];
  const totalPaginas = Math.max(1, Math.ceil(todosItens.length / POR_PAGINA));
  const paginaAtual = Math.min(pagina, totalPaginas);
  const itensNaPagina = todosItens.slice(
    (paginaAtual - 1) * POR_PAGINA,
    paginaAtual * POR_PAGINA,
  );

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <div className="page-pretitle">
              <Link to="/inventario">Inventário</Link>
            </div>
            <h2 className="page-title">{inv?.title ?? "Inventário"}</h2>
          </div>
          <div className="col-auto ms-auto">
            {isOpen && (
              <button
                className="btn btn-outline-primary"
                onClick={() => {
                  if (confirm("Fechar o inventário? Não poderá mais conferir itens.")) close.mutate();
                }}
              >
                Fechar inventário
              </button>
            )}
            {!isOpen && <span className="badge bg-secondary-lt">Fechado</span>}
          </div>
        </div>
      </div>

      <div className="row row-cards mt-1 mb-3">
        <Stat label="Total" value={report.data?.total ?? 0} cls="" />
        <Stat label="Conferidos" value={report.data?.found ?? 0} cls="text-green" />
        <Stat label="Não encontrados" value={report.data?.not_found ?? 0} cls="text-secondary" />
        <Stat label="Local divergente" value={report.data?.wrong_location ?? 0} cls="text-orange" />
      </div>

      <div className="card">
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th>Bem</th>
                <th>Local esperado</th>
                <th>Local encontrado</th>
                <th>Conferência</th>
                <th className="w-1" />
              </tr>
            </thead>
            <tbody>
              {itensNaPagina.map((it) => {
                const meta = DISCREPANCY_META[it.discrepancy];
                return (
                  <tr key={it.id}>
                    <td>
                      <div>{it.asset_name}</div>
                      <div className="asset-tag">{it.asset_tag}</div>
                    </td>
                    <td>{it.expected_location_name ?? "—"}</td>
                    <td>
                      {/* Bem que está com alguém: o portador é o local. */}
                      {it.holder_name ? (
                        <span className="d-inline-flex align-items-center gap-1">
                          <IconUser size={14} className="text-secondary" />
                          <span>Com {it.holder_name}</span>
                        </span>
                      ) : it.found ? (
                        (it.found_location_name ?? "—")
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      {it.found ? (
                        <span className={`badge ${meta.cls}`}>{meta.label}</span>
                      ) : (
                        <span className="text-secondary">Pendente</span>
                      )}
                    </td>
                    <td>
                      {isOpen && (
                        <button
                          className="btn btn-sm btn-success"
                          onClick={() => setScanning(it)}
                        >
                          {it.found ? "Reconferir" : "Conferir"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {todosItens.length > POR_PAGINA && (
          <Pagination
            page={paginaAtual}
            count={todosItens.length}
            label={{ one: "bem", many: "bens" }}
            pageSize={POR_PAGINA}
            onChange={setPagina}
          />
        )}
      </div>

      {scanning && (
        <ScanModal inventoryId={id} item={scanning} onClose={() => setScanning(null)} />
      )}
    </>
  );
}
