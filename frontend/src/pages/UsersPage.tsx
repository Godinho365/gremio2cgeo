import {
  IconEye,
  IconEyeOff,
  IconIdBadge2,
  IconKey,
  IconLock,
  IconPlus,
  IconSearch,
  IconTrash,
} from "@tabler/icons-react";
import { useEffect, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import Pagination from "../components/Pagination";
import {
  MILITARY_RANKS,
  ROLE_LABEL,
  ROLES,
  type UserRef,
  useCreateUser,
  useDeleteUser,
  useResetPassword,
  useUpdateUser,
  useUserPage,
} from "../features/accounts/api";
import { cpfValid, maskCpf, maskPhone, onlyDigits } from "../lib/masks";

const ROLE_HINT: Record<string, string> = {
  admin: "Acesso total: configura o sistema, aprova e gerencia usuários.",
  director: "Aprova reservas e cautelas; gerencia o patrimônio.",
  inventory: "Conduz os inventários periódicos.",
  user: "Solicita reservas e cautelas; vê os próprios registros.",
  auditor: "Somente leitura, para auditoria.",
};

function apiError(err: unknown, fallback: string): string {
  const data = (
    err as {
      response?: { data?: { error?: { message?: string; fields?: Record<string, string[]> } } };
    }
  ).response?.data?.error;
  return (data?.fields && Object.values(data.fields)[0]?.[0]) ?? data?.message ?? fallback;
}

function PasswordField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const [show, setShow] = useState(false);
  return (
    <>
      <label className="form-label required">{label}</label>
      <div className="input-icon">
        <span className="input-icon-addon">
          <IconLock size={16} />
        </span>
        <input
          type={show ? "text" : "password"}
          className="form-control"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          minLength={8}
          required
        />
        <button
          type="button"
          className="input-icon-addon border-0 bg-transparent p-0"
          onClick={() => setShow((s) => !s)}
          style={{ cursor: "pointer", left: "auto", right: 8, pointerEvents: "auto" }}
          title={show ? "Ocultar" : "Mostrar"}
          tabIndex={-1}
        >
          {show ? <IconEyeOff size={16} /> : <IconEye size={16} />}
        </button>
      </div>
      <small className="form-hint">Mínimo de 8 caracteres.</small>
    </>
  );
}

/** Cadastro e edição de usuário. Sem `user` = novo cadastro. */
function UserFormModal({ user, onClose }: { user?: UserRef; onClose: () => void }) {
  const { user: me } = useAuth();
  const create = useCreateUser();
  const update = useUpdateUser();
  const editing = !!user;
  const isSelf = editing && user.id === me?.id;

  const [form, setForm] = useState({
    full_name: user?.full_name ?? "",
    posto_graduacao: user?.posto_graduacao ?? "",
    nome_guerra: user?.nome_guerra ?? "",
    cpf: user?.cpf ? maskCpf(user.cpf) : "",
    birth_date: user?.birth_date ?? "",
    phone: user?.phone ? maskPhone(user.phone) : "",
    email: user?.email ?? "",
    password: "",
    role: user?.roles[0] ?? "user",
    is_active: user?.is_active ?? true,
  });
  const [error, setError] = useState<string | null>(null);
  const set = (k: string, v: string | boolean) => setForm((f) => ({ ...f, [k]: v }));

  const cpfBad = form.cpf.length > 0 && !cpfValid(form.cpf);
  const today = new Date().toISOString().slice(0, 10);
  const pending = create.isPending || update.isPending;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (cpfBad) {
      setError("CPF inválido.");
      return;
    }
    const common = {
      full_name: form.full_name.trim(),
      nome_guerra: form.nome_guerra.trim(),
      posto_graduacao: form.posto_graduacao,
      cpf: form.cpf ? onlyDigits(form.cpf) : "",
      birth_date: form.birth_date || null,
      phone: form.phone.trim(),
      email: form.email.trim(),
      role_codes: [form.role],
    };
    try {
      if (editing) {
        await update.mutateAsync({
          id: user.id,
          ...common,
          ...(isSelf ? {} : { is_active: form.is_active }),
        });
      } else {
        await create.mutateAsync({ ...common, password: form.password });
      }
      onClose();
    } catch (err) {
      setError(apiError(err, "Não foi possível salvar o usuário."));
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
                {editing ? `Editar — ${user.display_name}` : "Novo usuário"}
              </h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                {error && <div className="alert alert-danger">{error}</div>}

                <div className="text-uppercase text-secondary fw-bold small mb-2">
                  Identificação militar
                </div>
                <div className="mb-3">
                  <label className="form-label required">Nome completo</label>
                  <input
                    className="form-control"
                    value={form.full_name}
                    onChange={(e) => set("full_name", e.target.value)}
                    required
                    autoFocus
                  />
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
                  Aparece como{" "}
                  <strong>
                    {[form.posto_graduacao, form.nome_guerra].filter(Boolean).join(" ") ||
                      "(nome de guerra)"}
                  </strong>{" "}
                  nas cautelas e reservas.
                </div>
                <div className="row">
                  <div className="col-6 mb-3">
                    <label className="form-label">CPF</label>
                    <input
                      className={`form-control${cpfBad ? " is-invalid" : ""}`}
                      placeholder="000.000.000-00"
                      value={form.cpf}
                      onChange={(e) => set("cpf", maskCpf(e.target.value))}
                    />
                    {cpfBad && <div className="invalid-feedback">CPF inválido.</div>}
                  </div>
                  <div className="col-6 mb-3">
                    <label className="form-label">Data de nascimento</label>
                    <input
                      type="date"
                      className="form-control"
                      max={today}
                      value={form.birth_date ?? ""}
                      onChange={(e) => set("birth_date", e.target.value)}
                    />
                  </div>
                </div>

                <hr className="my-2" />
                <div className="text-uppercase text-secondary fw-bold small mb-2">Acesso</div>
                <div className="row">
                  <div className="col-6 mb-3">
                    <label className={`form-label${editing ? "" : " required"}`}>
                      E-mail (login)
                    </label>
                    <input
                      type="email"
                      className="form-control"
                      autoComplete="off"
                      placeholder="militar@exemplo.com"
                      value={form.email}
                      onChange={(e) => set("email", e.target.value)}
                      required={!editing}
                    />
                  </div>
                  <div className="col-6 mb-3">
                    {editing ? (
                      <>
                        <label className="form-label">Telefone</label>
                        <input
                          className="form-control"
                          placeholder="(00) 00000-0000"
                          value={form.phone}
                          onChange={(e) => set("phone", maskPhone(e.target.value))}
                        />
                      </>
                    ) : (
                      <PasswordField
                        label="Senha"
                        value={form.password}
                        onChange={(v) => set("password", v)}
                      />
                    )}
                  </div>
                </div>
                <div className="row">
                  {!editing && (
                    <div className="col-7 mb-2">
                      <label className="form-label">Telefone</label>
                      <input
                        className="form-control"
                        placeholder="(00) 00000-0000"
                        value={form.phone}
                        onChange={(e) => set("phone", maskPhone(e.target.value))}
                      />
                    </div>
                  )}
                  <div className={editing ? "col-6 mb-2" : "col-5 mb-2"}>
                    <label className="form-label">Perfil</label>
                    <select
                      className="form-select"
                      value={form.role}
                      onChange={(e) => set("role", e.target.value)}
                      disabled={isSelf}
                    >
                      {ROLES.map((r) => (
                        <option key={r.value} value={r.value}>
                          {r.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  {editing && (
                    <div className="col-6 mb-2">
                      <label className="form-label">Situação</label>
                      <select
                        className="form-select"
                        value={form.is_active ? "1" : "0"}
                        onChange={(e) => set("is_active", e.target.value === "1")}
                        disabled={isSelf}
                      >
                        <option value="1">Ativo</option>
                        <option value="0">Sem acesso</option>
                      </select>
                    </div>
                  )}
                </div>
                <div className="form-hint">
                  {isSelf
                    ? "Você não pode alterar o próprio perfil nem remover o próprio acesso."
                    : ROLE_HINT[form.role]}
                </div>
                {editing && !user.is_active && form.is_active && (
                  <div className="alert alert-warning mt-3 mb-0 py-2">
                    Depois de ativar, defina uma senha em <strong>Redefinir senha</strong> — sem
                    isso a pessoa ainda não consegue entrar.
                  </div>
                )}
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={pending}>
                  {pending ? "Salvando…" : editing ? "Salvar" : "Cadastrar usuário"}
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

function ResetPasswordModal({ user, onClose }: { user: UserRef; onClose: () => void }) {
  const reset = useResetPassword();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const mismatch = confirm.length > 0 && password !== confirm;
  const invalid = password.length < 8 || mismatch;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await reset.mutateAsync({ id: user.id, new_password: password });
      setDone(true);
    } catch (err) {
      setError(apiError(err, "Não foi possível redefinir a senha."));
    }
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered modal-sm">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title d-flex align-items-center gap-2">
                <IconKey size={20} />
                Redefinir senha
              </h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            {done ? (
              <>
                <div className="modal-body">
                  <div className="alert alert-success mb-0">
                    Senha de <strong>{user.display_name}</strong> redefinida. Informe a nova senha
                    a essa pessoa — ela pode trocá-la depois em Meu perfil.
                  </div>
                </div>
                <div className="modal-footer">
                  <button className="btn btn-primary" onClick={onClose}>
                    Fechar
                  </button>
                </div>
              </>
            ) : (
              <form onSubmit={submit}>
                <div className="modal-body">
                  {error && <div className="alert alert-danger">{error}</div>}
                  <div className="text-secondary mb-3">
                    Nova senha para <strong>{user.display_name}</strong>.
                  </div>
                  <div className="mb-3">
                    <PasswordField label="Nova senha" value={password} onChange={setPassword} />
                  </div>
                  <div className="mb-1">
                    <label className="form-label required">Confirmar</label>
                    <input
                      type="password"
                      className={`form-control${mismatch ? " is-invalid" : ""}`}
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                      required
                    />
                    {mismatch && <div className="invalid-feedback">As senhas não conferem.</div>}
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-link" onClick={onClose}>
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={invalid || reset.isPending}
                  >
                    {reset.isPending ? "Salvando…" : "Redefinir"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      </div>
      <div className="modal-backdrop fade show" />
    </>
  );
}

export default function UsersPage() {
  const { user: me } = useAuth();
  const del = useDeleteUser();
  const [erro, setErro] = useState<string | null>(null);
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [active, setActive] = useState("");
  const [page, setPage] = useState(1);
  const [form, setForm] = useState<{ user?: UserRef } | null>(null);
  const [resetting, setResetting] = useState<UserRef | null>(null);

  // Busca com debounce (350ms), como nas demais listagens.
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(qInput);
      setPage(1);
    }, 350);
    return () => clearTimeout(t);
  }, [qInput]);

  const { data, isLoading, isFetching } = useUserPage({
    q: q || undefined,
    role: role || undefined,
    is_active: active || undefined,
    page,
  });
  const rows = data?.results ?? [];
  const count = data?.count ?? 0;
  const hasFilter = !!q || !!role || !!active;

  async function removeUser(u: UserRef) {
    if (!confirm(`Excluir o cadastro de ${u.display_name}?`)) return;
    setErro(null);
    try {
      await del.mutateAsync(u.id);
    } catch (e) {
      setErro(apiError(e, "Não foi possível excluir o usuário."));
    }
  }

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <div className="page-pretitle">Equipe &amp; acesso</div>
            <h2 className="page-title">Usuários</h2>
          </div>
          <div className="col-auto ms-auto">
            <button className="btn btn-primary" onClick={() => setForm({})}>
              <IconPlus size={18} className="me-1" />
              Novo usuário
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
        <div className="card-header">
          <div className="row w-100 g-2 align-items-center">
            <div className="col">
              <div className="input-icon">
                <span className="input-icon-addon">
                  <IconSearch size={16} />
                </span>
                <input
                  className="form-control"
                  placeholder="Buscar por nome, nome de guerra, posto ou e-mail…"
                  value={qInput}
                  onChange={(e) => setQInput(e.target.value)}
                />
              </div>
            </div>
            <div className="col-auto">
              <select
                className="form-select"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="">Todos os perfis</option>
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="col-auto">
              <select
                className="form-select"
                value={active}
                onChange={(e) => setActive(e.target.value)}
              >
                <option value="">Todas as situações</option>
                <option value="true">Ativos</option>
                <option value="false">Sem acesso</option>
              </select>
            </div>
            {hasFilter && (
              <div className="col-auto">
                <button
                  className="btn btn-link"
                  onClick={() => {
                    setQInput("");
                    setQ("");
                    setRole("");
                    setActive("");
                  }}
                >
                  Limpar
                </button>
              </div>
            )}
          </div>
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
              {!isLoading && rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-secondary text-center py-4">
                    {hasFilter ? "Nenhum usuário para os filtros." : "Nenhum usuário cadastrado."}
                  </td>
                </tr>
              )}
              {rows.map((u) => {
                const initials = (u.nome_guerra || u.full_name || u.username || "?")
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
                        <div className="lh-sm">
                          <div className="fw-medium">{u.nome_guerra || u.username}</div>
                          {u.full_name && (
                            <div className="text-secondary small">{u.full_name}</div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="text-secondary">{u.email || u.username}</td>
                    <td>
                      {u.roles.map((r) => (
                        <span key={r} className="badge bg-blue-lt me-1">
                          {ROLE_LABEL[r] ?? r}
                        </span>
                      ))}
                    </td>
                    <td>
                      <span className={`badge ${u.is_active ? "bg-green-lt" : "bg-secondary-lt"}`}>
                        {u.is_active ? "Ativo" : "Sem acesso"}
                      </span>
                    </td>
                    <td>
                      <div className="btn-list flex-nowrap justify-content-end">
                        <button
                          className="btn btn-sm btn-ghost-secondary"
                          onClick={() => setForm({ user: u })}
                        >
                          Editar
                        </button>
                        <button
                          className="btn btn-sm btn-ghost-secondary"
                          title="Redefinir senha"
                          onClick={() => setResetting(u)}
                        >
                          <IconKey size={16} />
                        </button>
                        <button
                          className="btn btn-sm btn-icon btn-ghost-danger"
                          title={u.id === me?.id ? "Você não pode se excluir" : "Excluir cadastro"}
                          disabled={u.id === me?.id || del.isPending}
                          onClick={() => removeUser(u)}
                        >
                          <IconTrash size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <Pagination
          page={page}
          count={count}
          label={{ one: "usuário", many: "usuários" }}
          loading={isFetching && !isLoading}
          onChange={setPage}
        />
      </div>

      {form && <UserFormModal user={form.user} onClose={() => setForm(null)} />}
      {resetting && (
        <ResetPasswordModal user={resetting} onClose={() => setResetting(null)} />
      )}
    </>
  );
}
