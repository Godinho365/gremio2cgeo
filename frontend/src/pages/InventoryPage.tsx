import { IconPencil, IconPlus, IconTrash } from "@tabler/icons-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  type Inventory,
  useDeleteInventory,
  useInventories,
  useOpenInventory,
  useRenameInventory,
} from "../features/inventory/api";

function fmt(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString("pt-BR") : "—";
}

/** "2026-08-01" → "agosto de 2026". */
function mesDeReferencia(iso: string | null): string {
  if (!iso) return "—";
  const [ano, mes] = iso.split("-").map(Number);
  return new Date(ano, mes - 1, 1).toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
  });
}

/** Sugestão do título: a conferência é mensal. */
function tituloDoMes(): string {
  const mes = new Date().toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
  return `Inventário de ${mes}`;
}

export default function InventoryPage() {
  const { data, isLoading } = useInventories();
  const open = useOpenInventory();
  const rename = useRenameInventory();
  const del = useDeleteInventory();
  const navigate = useNavigate();
  const [title, setTitle] = useState(tituloDoMes());
  const [showNew, setShowNew] = useState(false);
  const [editando, setEditando] = useState<Inventory | null>(null);
  const [novoTitulo, setNovoTitulo] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    const inv = await open.mutateAsync(title);
    setShowNew(false);
    setTitle(tituloDoMes());
    navigate(`/inventario/${inv.id}`);
  }

  async function salvarTitulo(e: React.FormEvent) {
    e.preventDefault();
    if (!editando || !novoTitulo.trim()) return;
    setErro(null);
    try {
      await rename.mutateAsync({ id: editando.id, title: novoTitulo.trim() });
      setEditando(null);
    } catch (err) {
      setErro(
        (err as { response?: { data?: { error?: { message?: string } } } }).response?.data?.error
          ?.message ?? "Não foi possível renomear.",
      );
    }
  }

  async function excluir(inv: Inventory) {
    if (!confirm(`Excluir “${inv.title}”? A conferência inteira é descartada.`)) return;
    setErro(null);
    try {
      await del.mutateAsync(inv.id);
    } catch (err) {
      setErro(
        (err as { response?: { data?: { error?: { message?: string } } } }).response?.data?.error
          ?.message ?? "Não foi possível excluir.",
      );
    }
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

      {erro && (
        <div className="alert alert-danger mt-3 d-flex align-items-center">
          <span className="flex-fill">{erro}</span>
          <button className="btn btn-sm btn-ghost-secondary" onClick={() => setErro(null)}>
            Fechar
          </button>
        </div>
      )}

      <div className="card mt-3">
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th>Mês</th>
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
                  <td colSpan={6} className="text-secondary">
                    Carregando…
                  </td>
                </tr>
              )}
              {!isLoading && data?.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-secondary">
                    Nenhum inventário. Clique em “Novo inventário” para iniciar.
                  </td>
                </tr>
              )}
              {data?.results.map((inv) => (
                <tr key={inv.id}>
                  <td className="asset-tag text-nowrap">{mesDeReferencia(inv.reference_month)}</td>
                  <td>
                    <button
                      className="btn btn-link p-0 text-reset fw-medium text-start"
                      onClick={() => navigate(`/inventario/${inv.id}`)}
                    >
                      {inv.title}
                    </button>
                  </td>
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
                    <div className="btn-list flex-nowrap justify-content-end">
                      <button
                        className="btn btn-sm btn-icon btn-ghost-secondary"
                        title="Renomear"
                        onClick={() => {
                          setEditando(inv);
                          setNovoTitulo(inv.title);
                        }}
                      >
                        <IconPencil size={16} />
                      </button>
                      <button
                        className="btn btn-sm btn-icon btn-ghost-danger"
                        title="Excluir inventário"
                        disabled={del.isPending}
                        onClick={() => void excluir(inv)}
                      >
                        <IconTrash size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {editando && (
        <>
          <div className="modal modal-blur show d-block" tabIndex={-1}>
            <div className="modal-dialog modal-dialog-centered modal-sm">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">Renomear inventário</h5>
                  <button type="button" className="btn-close" onClick={() => setEditando(null)} />
                </div>
                <form onSubmit={salvarTitulo}>
                  <div className="modal-body">
                    <label className="form-label required">Título</label>
                    <input
                      className="form-control"
                      value={novoTitulo}
                      onChange={(e) => setNovoTitulo(e.target.value)}
                      autoFocus
                      required
                    />
                    <small className="form-hint">
                      Mês de referência: {mesDeReferencia(editando.reference_month)}.
                    </small>
                  </div>
                  <div className="modal-footer">
                    <button type="button" className="btn btn-link" onClick={() => setEditando(null)}>
                      Cancelar
                    </button>
                    <button type="submit" className="btn btn-primary" disabled={rename.isPending}>
                      {rename.isPending ? "Salvando…" : "Salvar"}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
          <div className="modal-backdrop fade show" />
        </>
      )}

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
