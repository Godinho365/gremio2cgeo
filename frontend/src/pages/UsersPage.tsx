import { IconPlus } from "@tabler/icons-react";
import { useState } from "react";

import { ROLE_LABEL, ROLES, useCreateUser, useUsers } from "../features/accounts/api";

function NewUserModal({ onClose }: { onClose: () => void }) {
  const create = useCreateUser();
  const [form, setForm] = useState({
    posto_graduacao: "",
    nome_guerra: "",
    username: "",
    password: "",
    email: "",
    role: "user",
  });
  const [error, setError] = useState<string | null>(null);
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await create.mutateAsync({
        username: form.username,
        password: form.password,
        email: form.email || undefined,
        nome_guerra: form.nome_guerra,
        posto_graduacao: form.posto_graduacao,
        role_codes: [form.role],
      });
      onClose();
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response
        ?.data?.error?.message;
      setError(msg ?? "Não foi possível cadastrar o usuário.");
    }
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Novo usuário</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                {error && <div className="alert alert-danger">{error}</div>}
                <div className="row">
                  <div className="col-4 mb-3">
                    <label className="form-label">Posto/Grad.</label>
                    <input
                      className="form-control"
                      placeholder="Cap, Sd…"
                      value={form.posto_graduacao}
                      onChange={(e) => set("posto_graduacao", e.target.value)}
                    />
                  </div>
                  <div className="col-8 mb-3">
                    <label className="form-label">Nome de guerra</label>
                    <input
                      className="form-control"
                      value={form.nome_guerra}
                      onChange={(e) => set("nome_guerra", e.target.value)}
                    />
                  </div>
                </div>
                <div className="row">
                  <div className="col-6 mb-3">
                    <label className="form-label required">Usuário (login)</label>
                    <input
                      className="form-control"
                      value={form.username}
                      onChange={(e) => set("username", e.target.value)}
                      required
                    />
                  </div>
                  <div className="col-6 mb-3">
                    <label className="form-label required">Senha</label>
                    <input
                      type="password"
                      className="form-control"
                      value={form.password}
                      onChange={(e) => set("password", e.target.value)}
                      minLength={8}
                      required
                    />
                  </div>
                </div>
                <div className="row">
                  <div className="col-7 mb-1">
                    <label className="form-label">E-mail</label>
                    <input
                      type="email"
                      className="form-control"
                      value={form.email}
                      onChange={(e) => set("email", e.target.value)}
                    />
                  </div>
                  <div className="col-5 mb-1">
                    <label className="form-label">Perfil</label>
                    <select
                      className="form-select"
                      value={form.role}
                      onChange={(e) => set("role", e.target.value)}
                    >
                      {ROLES.map((r) => (
                        <option key={r.value} value={r.value}>
                          {r.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={create.isPending}>
                  {create.isPending ? "Salvando…" : "Cadastrar"}
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

export default function UsersPage() {
  const { data, isLoading } = useUsers();
  const [showNew, setShowNew] = useState(false);

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <h2 className="page-title">Usuários</h2>
          </div>
          <div className="col-auto ms-auto">
            <button className="btn btn-primary" onClick={() => setShowNew(true)}>
              <IconPlus size={18} className="me-1" />
              Novo usuário
            </button>
          </div>
        </div>
      </div>

      <div className="card mt-3">
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th>Posto/Grad.</th>
                <th>Nome de guerra</th>
                <th>Login</th>
                <th>Perfil</th>
                <th>Situação</th>
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
              {data?.map((u) => (
                <tr key={u.id}>
                  <td>{u.posto_graduacao || "—"}</td>
                  <td className="fw-bold">{u.nome_guerra || u.username}</td>
                  <td className="text-secondary">{u.username}</td>
                  <td>{u.roles.map((r) => ROLE_LABEL[r] ?? r).join(", ")}</td>
                  <td>
                    <span className={`badge ${u.is_active ? "bg-green-lt" : "bg-secondary-lt"}`}>
                      {u.is_active ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showNew && <NewUserModal onClose={() => setShowNew(false)} />}
    </>
  );
}
