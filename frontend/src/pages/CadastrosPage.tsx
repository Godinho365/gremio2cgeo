import { IconCheck, IconPencil, IconPlus, IconTrash, IconX } from "@tabler/icons-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import {
  type NamedRef,
  useCategories,
  useCreateCategory,
  useCreateLocation,
  useDeleteCategory,
  useDeleteLocation,
  useLocations,
  useRenameCategory,
  useRenameLocation,
} from "../features/assets/api";

function apiError(err: unknown, fallback: string): string {
  const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response?.data
    ?.error?.message;
  return msg ?? fallback;
}

/**
 * Lista editável de categorias/localizações. A contagem de bens fica visível
 * porque é ela que decide se o registro pode sair: excluir um que está em uso
 * deixaria bens apontando para o nada.
 */
function RegistryCard({
  title,
  hint,
  placeholder,
  items,
  filterTo,
  onCreate,
  onRename,
  onDelete,
  pending,
}: {
  title: string;
  hint: string;
  placeholder: string;
  items: NamedRef[] | undefined;
  /** Link para a lista de bens já filtrada por este registro. */
  filterTo: (item: NamedRef) => string;
  onCreate: (name: string) => Promise<unknown>;
  onRename: (id: string, name: string) => Promise<unknown>;
  onDelete: (id: string) => Promise<unknown>;
  pending: boolean;
}) {
  const [novo, setNovo] = useState("");
  const [editandoId, setEditandoId] = useState<string | null>(null);
  const [rascunho, setRascunho] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  const nomeRepetido = (nome: string, exceto?: string) =>
    (items ?? []).some(
      (i) => i.id !== exceto && i.name.trim().toLowerCase() === nome.trim().toLowerCase(),
    );

  async function criar(e: React.FormEvent) {
    e.preventDefault();
    const nome = novo.trim();
    if (!nome) return;
    setErro(null);
    if (nomeRepetido(nome)) {
      setErro(`“${nome}” já está na lista.`);
      return;
    }
    try {
      await onCreate(nome);
      setNovo("");
    } catch (err) {
      setErro(apiError(err, "Não foi possível adicionar."));
    }
  }

  async function salvar(item: NamedRef) {
    const nome = rascunho.trim();
    if (!nome || nome === item.name) {
      setEditandoId(null);
      return;
    }
    setErro(null);
    if (nomeRepetido(nome, item.id)) {
      setErro(`“${nome}” já está na lista.`);
      return;
    }
    try {
      await onRename(item.id, nome);
      setEditandoId(null);
    } catch (err) {
      setErro(apiError(err, "Não foi possível renomear."));
    }
  }

  async function excluir(item: NamedRef) {
    if (!confirm(`Excluir “${item.name}”?`)) return;
    setErro(null);
    try {
      await onDelete(item.id);
    } catch (err) {
      setErro(apiError(err, "Não foi possível excluir."));
    }
  }

  return (
    <div className="card h-100">
      <div className="card-header">
        <h3 className="card-title">{title}</h3>
        <span className="card-actions text-secondary small">{items?.length ?? 0}</span>
      </div>
      <div className="card-body">
        <form className="d-flex gap-2" onSubmit={criar}>
          <input
            className="form-control"
            placeholder={placeholder}
            value={novo}
            onChange={(e) => setNovo(e.target.value)}
          />
          <button className="btn btn-primary flex-shrink-0" disabled={pending || !novo.trim()}>
            <IconPlus size={16} className="me-1" />
            Adicionar
          </button>
        </form>
        <div className="form-hint mt-2">{hint}</div>

        {erro && (
          <div className="alert alert-danger mt-3 mb-0 py-2 d-flex align-items-center">
            <span className="flex-fill">{erro}</span>
            <button className="btn btn-sm btn-ghost-secondary" onClick={() => setErro(null)}>
              Fechar
            </button>
          </div>
        )}
      </div>

      <ul className="list-group list-group-flush">
        {items?.length === 0 && (
          <li className="list-group-item text-secondary">
            Nada cadastrado ainda. Comece pelo campo acima.
          </li>
        )}
        {items?.map((item) => {
          const emUso = item.asset_count > 0;
          return (
            <li key={item.id} className="list-group-item d-flex align-items-center gap-2">
              {editandoId === item.id ? (
                <>
                  <input
                    className="form-control form-control-sm"
                    value={rascunho}
                    autoFocus
                    onChange={(e) => setRascunho(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") void salvar(item);
                      if (e.key === "Escape") setEditandoId(null);
                    }}
                  />
                  <button
                    className="btn btn-sm btn-icon btn-primary"
                    title="Salvar"
                    onClick={() => void salvar(item)}
                  >
                    <IconCheck size={16} />
                  </button>
                  <button
                    className="btn btn-sm btn-icon btn-ghost-secondary"
                    title="Cancelar"
                    onClick={() => setEditandoId(null)}
                  >
                    <IconX size={16} />
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    className="flex-fill text-start border-0 bg-transparent p-0"
                    title="Renomear"
                    onClick={() => {
                      setEditandoId(item.id);
                      setRascunho(item.name);
                    }}
                  >
                    {item.name}
                  </button>
                  {emUso ? (
                    <Link to={filterTo(item)} className="badge bg-secondary-lt text-decoration-none">
                      {item.asset_count} {item.asset_count === 1 ? "bem" : "bens"}
                    </Link>
                  ) : (
                    <span className="text-secondary small">sem bens</span>
                  )}
                  <button
                    className="btn btn-sm btn-icon btn-ghost-secondary"
                    title="Renomear"
                    onClick={() => {
                      setEditandoId(item.id);
                      setRascunho(item.name);
                    }}
                  >
                    <IconPencil size={16} />
                  </button>
                  <button
                    className="btn btn-sm btn-icon btn-ghost-danger"
                    title={emUso ? "Em uso: troque os bens antes de excluir" : "Excluir"}
                    disabled={emUso || pending}
                    onClick={() => void excluir(item)}
                  >
                    <IconTrash size={16} />
                  </button>
                </>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function CadastrosPage() {
  const categorias = useCategories();
  const locais = useLocations();
  const criarCategoria = useCreateCategory();
  const renomearCategoria = useRenameCategory();
  const excluirCategoria = useDeleteCategory();
  const criarLocal = useCreateLocation();
  const renomearLocal = useRenameLocation();
  const excluirLocal = useDeleteLocation();

  return (
    <>
      <div className="page-header">
        <div className="page-pretitle">Configurações do catálogo</div>
        <h2 className="page-title">Cadastros</h2>
      </div>
      <div className="row row-cards mt-1">
        <div className="col-md-6">
          <RegistryCard
            title="Tipos de bem"
            hint="Aparecem como filtro no catálogo e no patrimônio."
            placeholder="Ex.: Jogos de tabuleiro"
            items={categorias.data}
            filterTo={(c) => `/patrimonio?category=${c.id}`}
            onCreate={(nome) => criarCategoria.mutateAsync(nome)}
            onRename={(id, name) => renomearCategoria.mutateAsync({ id, name })}
            onDelete={(id) => excluirCategoria.mutateAsync(id)}
            pending={criarCategoria.isPending || excluirCategoria.isPending}
          />
        </div>
        <div className="col-md-6">
          <RegistryCard
            title="Localizações"
            hint="Onde o bem fica guardado."
            placeholder="Ex.: Almoxarifado"
            items={locais.data}
            filterTo={(l) => `/patrimonio?location=${l.id}`}
            onCreate={(nome) => criarLocal.mutateAsync(nome)}
            onRename={(id, name) => renomearLocal.mutateAsync({ id, name })}
            onDelete={(id) => excluirLocal.mutateAsync(id)}
            pending={criarLocal.isPending || excluirLocal.isPending}
          />
        </div>
      </div>
    </>
  );
}
