import { IconEye, IconEyeOff, IconIdBadge2, IconLock, IconPlus } from "@tabler/icons-react";
import { useState } from "react";

import { MILITARY_RANKS, ROLE_LABEL, ROLES, useCreateUser, useUsers } from "../features/accounts/api";

const ROLE_HINT: Record<string, string> = {
  admin: "Acesso total: configura o sistema, aprova e gerencia usuários.",
  director: "Aprova reservas e cautelas; gerencia o patrimônio.",
  inventory: "Conduz os inventários periódicos.",
  user: "Solicita reservas e cautelas; vê os próprios registros.",
  auditor: "Somente leitura, para auditoria.",
};

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
  const [showPwd, setShowPwd] = useState(false);
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
            <div className="modal-status-top bg-primary" />
            <div className="modal-header">
              <h5 className="modal-title d-flex align-items-center gap-2">
                <IconIdBadge2 size={20} />
                Novo usuário
              </h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                {error && <div className="alert alert-danger">{error}</div>}

                <div className="text-uppercase text-secondary fw-bold small mb-2">
                  Identificação militar
                </div>
                <div className="row">
                  <div className="col-5 mb-3">
                    <label className="form-label">Posto/Grad.</label>
                    <select
                      className="form-select"
                      value={form.posto_graduacao}
                      onChange={(e) => set("posto_graduacao", e.target.value)}
                    >
                      <option value="">Selecione…</option>
                      {MILITARY_RANKS.map((g) => (
                        <optgroup key={g.group} label={g.group}>
                          {g.items.map((r) => (
                            <option key={r.value} value={r.value}>
                              {r.label} ({r.value})
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </div>
                  <div className="col-7 mb-3">
                    <label className="form-label">Nome de guerra</label>
                    <input
                      className="form-control"
                      placeholder="SILVA"
                      value={form.nome_guerra}
                      onChange={(e) => set("nome_guerra", e.target.value.toUpperCase())}
                    />
                  </div>
                </div>
                <div className="form-hint mb-3">
                  Aparece como <strong>{[form.posto_graduacao, form.nome_guerra].filter(Boolean).join(" ") || "(nome de guerra)"}</strong> nas cautelas e reservas.
                </div>

                <hr className="my-2" />
                <div className="text-uppercase text-secondary fw-bold small mb-2">Acesso</div>
                <div className="row">
                  <div className="col-6 mb-3">
                    <label className="form-label required">Usuário (login)</label>
                    <input
                      className="form-control"
                      autoComplete="off"
                      value={form.username}
                      onChange={(e) => set("username", e.target.value)}
                      required
                    />
                  </div>
                  <div className="col-6 mb-3">
                    <label className="form-label required">Senha</label>
                    <div className="input-icon">
                      <span className="input-icon-addon">
                        <IconLock size={16} />
                      </span>
                      <input
                        type={showPwd ? "text" : "password"}
                        className="form-control"
                        value={form.password}
                        onChange={(e) => set("password", e.target.value)}
                        minLength={8}
                        required
                      />
                      <button
                        type="button"
                        className="input-icon-addon border-0 bg-transparent p-0"
                        onClick={() => setShowPwd((s) => !s)}
                        style={{ cursor: "pointer", left: "auto", right: 8, pointerEvents: "auto" }}
                        title={showPwd ? "Ocultar" : "Mostrar"}
                        tabIndex={-1}
                      >
                        {showPwd ? <IconEyeOff size={16} /> : <IconEye size={16} />}
                      </button>
                    </div>
                    <small className="form-hint">Mínimo de 8 caracteres.</small>
                  </div>
                </div>
                <div className="row">
                  <div className="col-7 mb-2">
                    <label className="form-label">E-mail</label>
                    <input
                      type="email"
                      className="form-control"
                      placeholder="opcional"
                      value={form.email}
                      onChange={(e) => set("email", e.target.value)}
                    />
                  </div>
                  <div className="col-5 mb-2">
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
                <div className="form-hint">{ROLE_HINT[form.role]}</div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={create.isPending}>
                  {create.isPending ? "Salvando…" : "Cadastrar usuário"}
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
            <div className="page-pretitle">Equipe &amp; acesso</div>
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
        <div className="card-header">
          <h3 className="card-title">
            {data?.length ?? 0} {(data?.length ?? 0) === 1 ? "usuário" : "usuários"}
          </h3>
        </div>
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
              {data?.map((u) => {
                const initials = (u.nome_guerra || u.username || "?")
                  .split(/\s+/)
                  .map((p) => p[0])
                  .slice(0, 2)
                  .join("")
                  .toUpperCase();
                return (
                  <tr key={u.id}>
                    <td>{u.posto_graduacao || "—"}</td>
                    <td>
                      <div className="d-flex align-items-center">
                        <span className="avatar avatar-sm me-2 bg-primary-lt">{initials}</span>
                        <span className="fw-medium">{u.nome_guerra || u.username}</span>
                      </div>
                    </td>
                    <td className="text-secondary">{u.username}</td>
                    <td>
                      {u.roles.map((r) => (
                        <span key={r} className="badge bg-blue-lt me-1">
                          {ROLE_LABEL[r] ?? r}
                        </span>
                      ))}
                    </td>
                    <td>
                      <span className={`badge ${u.is_active ? "bg-green-lt" : "bg-secondary-lt"}`}>
                        {u.is_active ? "Ativo" : "Inativo"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {showNew && <NewUserModal onClose={() => setShowNew(false)} />}
    </>
  );
}
