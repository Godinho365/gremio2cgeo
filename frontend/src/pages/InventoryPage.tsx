import { IconPlus } from "@tabler/icons-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useInventories, useOpenInventory } from "../features/inventory/api";

function fmt(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString("pt-BR") : "—";
}

export default function InventoryPage() {
  const { data, isLoading } = useInventories();
  const open = useOpenInventory();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [showNew, setShowNew] = useState(false);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    const inv = await open.mutateAsync(title);
    setShowNew(false);
    setTitle("");
    navigate(`/inventario/${inv.id}`);
  }

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <div className="page-pretitle">Conferência periódica (Art. 30 b)</div>
            <h2 className="page-title">Inventário</h2>
          </div>
          <div className="col-auto ms-auto">
            <button className="btn btn-primary" onClick={() => setShowNew(true)}>
              <IconPlus size={18} className="me-1" />
              Novo inventário
            </button>
          </div>
        </div>
      </div>

      <div className="card mt-3">
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th>Título</th>
                <th>Responsável</th>
                <th>Aberto em</th>
                <th>Situação</th>
                <th className="w-1" />
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
                    Nenhum inventário. Clique em “Novo inventário” para iniciar.
                  </td>
                </tr>
              )}
              {data?.results.map((inv) => (
                <tr
                  key={inv.id}
                  style={{ cursor: "pointer" }}
                  onClick={() => navigate(`/inventario/${inv.id}`)}
                >
                  <td className="fw-bold">{inv.title}</td>
                  <td>{inv.responsible_name}</td>
                  <td>{fmt(inv.created_at)}</td>
                  <td>
                    <span
                      className={`badge ${inv.status === "open" ? "bg-green-lt" : "bg-secondary-lt"}`}
                    >
                      {inv.status === "open" ? "Em andamento" : "Fechado"}
                    </span>
                  </td>
                  <td>
                    <span className="text-secondary">Abrir →</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showNew && (
        <>
          <div className="modal modal-blur show d-block" tabIndex={-1}>
            <div className="modal-dialog modal-dialog-centered modal-sm">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">Novo inventário</h5>
                  <button type="button" className="btn-close" onClick={() => setShowNew(false)} />
                </div>
                <form onSubmit={create}>
                  <div className="modal-body">
                    <label className="form-label required">Título</label>
                    <input
                      className="form-control"
                      placeholder="Ex.: Inventário Anual 2026"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      autoFocus
                      required
                    />
                    <small className="form-hint">
                      Serão gerados itens para todos os bens ativos.
                    </small>
                  </div>
                  <div className="modal-footer">
                    <button type="button" className="btn btn-link" onClick={() => setShowNew(false)}>
                      Cancelar
                    </button>
                    <button type="submit" className="btn btn-primary" disabled={open.isPending}>
                      {open.isPending ? "Abrindo…" : "Abrir inventário"}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
          <div className="modal-backdrop fade show" />
        </>
      )}
    </>
  );
}
