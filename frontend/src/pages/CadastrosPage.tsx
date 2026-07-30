import { useState } from "react";

import {
  LOCATION_TYPES,
  useCategories,
  useCreateCategory,
  useCreateLocation,
  useLocations,
} from "../features/assets/api";

function CategoriesCard() {
  const { data } = useCategories();
  const create = useCreateCategory();
  const [name, setName] = useState("");

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    await create.mutateAsync(name.trim());
    setName("");
  }

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">Categorias</h3>
      </div>
      <div className="card-body">
        <form className="d-flex gap-2 mb-3" onSubmit={add}>
          <input
            className="form-control"
            placeholder="Nova categoria (ex.: TI, Mobiliário)"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <button className="btn btn-primary" disabled={create.isPending}>
            Adicionar
          </button>
        </form>
        <ul className="list-group list-group-flush">
          {data?.map((c) => (
            <li key={c.id} className="list-group-item px-0">
              {c.name}
            </li>
          ))}
          {data?.length === 0 && <li className="list-group-item px-0 text-secondary">Nenhuma.</li>}
        </ul>
      </div>
    </div>
  );
}

function LocationsCard() {
  const { data } = useLocations();
  const create = useCreateLocation();
  const [name, setName] = useState("");
  const [type, setType] = useState("room");

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    await create.mutateAsync({ name: name.trim(), type });
    setName("");
  }

  const typeLabel = (t?: string) => LOCATION_TYPES.find((x) => x.value === t)?.label ?? t ?? "";

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">Localizações</h3>
      </div>
      <div className="card-body">
        <form className="d-flex gap-2 mb-3" onSubmit={add}>
          <input
            className="form-control"
            placeholder="Nova localização (ex.: Almoxarifado)"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <select
            className="form-select"
            style={{ maxWidth: 140 }}
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            {LOCATION_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
          <button className="btn btn-primary" disabled={create.isPending}>
            Adicionar
          </button>
        </form>
        <ul className="list-group list-group-flush">
          {data?.map((l) => (
            <li key={l.id} className="list-group-item px-0 d-flex justify-content-between">
              <span>{l.name}</span>
              <span className="badge bg-secondary-lt">{typeLabel(l.type)}</span>
            </li>
          ))}
          {data?.length === 0 && <li className="list-group-item px-0 text-secondary">Nenhuma.</li>}
        </ul>
      </div>
    </div>
  );
}

export default function CadastrosPage() {
  return (
    <>
      <div className="page-header">
        <h2 className="page-title">Cadastros</h2>
      </div>
      <div className="row row-cards mt-1">
        <div className="col-md-6">
          <CategoriesCard />
        </div>
        <div className="col-md-6">
          <LocationsCard />
        </div>
      </div>
    </>
  );
}
