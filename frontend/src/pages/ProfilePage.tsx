import { IconLock, IconReceipt2, IconUser, IconWallet } from "@tabler/icons-react";
import { useState } from "react";

import { useAuth } from "../auth/AuthContext";
import { ORG_NAME } from "../branding";
import {
  MILITARY_RANKS,
  ROLE_LABEL,
  useChangePassword,
  useUpdateProfile,
} from "../features/accounts/api";
import { brl, useCredits } from "../features/barbershop/api";
import {
  FINANCIAL_STATUS_BADGE,
  FINANCIAL_STATUS_LABEL,
  useMyFinance,
} from "../features/finance/api";
import { formatDateBr, maskCpf, maskPhone } from "../lib/masks";

function apiMessage(err: unknown, fallback: string): string {
  const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response?.data
    ?.error?.message;
  return msg ?? fallback;
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="datagrid-item">
      <div className="datagrid-title">{label}</div>
      <div className="datagrid-content">{value || "—"}</div>
    </div>
  );
}

function ProfileForm() {
  const { user, refresh } = useAuth();
  const update = useUpdateProfile();
  const [form, setForm] = useState({
    nome_guerra: user?.nome_guerra ?? "",
    posto_graduacao: user?.posto_graduacao ?? "",
    email: user?.email ?? "",
    phone: maskPhone(user?.phone ?? ""),
  });
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const set = (k: keyof typeof form, v: string) => {
    setForm((f) => ({ ...f, [k]: v }));
    setSaved(false);
  };

  const emailChanged = form.email.trim().toLowerCase() !== (user?.email ?? "").toLowerCase();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    try {
      await update.mutateAsync({
        nome_guerra: form.nome_guerra.trim(),
        posto_graduacao: form.posto_graduacao,
        email: form.email.trim(),
        phone: form.phone.trim(),
      });
      await refresh();
      setSaved(true);
    } catch (err) {
      setError(apiMessage(err, "Não foi possível salvar as alterações."));
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <div className="card-header">
        <h3 className="card-title">Meus dados</h3>
      </div>
      <div className="card-body">
        {error && <div className="alert alert-danger">{error}</div>}
        {saved && <div className="alert alert-success">Dados atualizados.</div>}
        <div className="row g-3">
          <div className="col-md-6">
            <label className="form-label">Posto/Graduação</label>
            <select
              className="form-select"
              value={form.posto_graduacao}
              onChange={(e) => set("posto_graduacao", e.target.value)}
            >
              <option value="">(não informado)</option>
              {MILITARY_RANKS.map((grupo) => (
                <optgroup key={grupo.group} label={grupo.group}>
                  {grupo.items.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <div className="form-hint">Atualize aqui quando for promovido.</div>
          </div>
          <div className="col-md-6">
            <label className="form-label">Nome de guerra</label>
            <input
              className="form-control"
              value={form.nome_guerra}
              maxLength={60}
              onChange={(e) => set("nome_guerra", e.target.value.toUpperCase())}
            />
          </div>
          <div className="col-md-6">
            <label className="form-label">Telefone</label>
            <input
              className="form-control"
              placeholder="(00) 00000-0000"
              value={form.phone}
              onChange={(e) => set("phone", maskPhone(e.target.value))}
            />
          </div>
          <div className="col-12">
            <label className="form-label required">E-mail</label>
            <input
              type="email"
              className="form-control"
              value={form.email}
              onChange={(e) => set("email", e.target.value)}
              required
            />
            {emailChanged && (
              <div className="form-hint text-warning">
                O e-mail também é o seu login — depois de salvar, use o novo endereço para entrar.
              </div>
            )}
          </div>
        </div>
      </div>
      <div className="card-footer text-end">
        <button type="submit" className="btn btn-primary" disabled={update.isPending}>
          {update.isPending ? "Salvando…" : "Salvar alterações"}
        </button>
      </div>
    </form>
  );
}

function PasswordForm() {
  const change = useChangePassword();
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const set = (k: keyof typeof form, v: string) => {
    setForm((f) => ({ ...f, [k]: v }));
    setSaved(false);
  };

  const tooShort = form.next.length > 0 && form.next.length < 8;
  const mismatch = form.confirm.length > 0 && form.next !== form.confirm;
  const invalid = !form.current || !form.next || tooShort || mismatch;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    try {
      await change.mutateAsync({ current_password: form.current, new_password: form.next });
      setForm({ current: "", next: "", confirm: "" });
      setSaved(true);
    } catch (err) {
      setError(apiMessage(err, "Não foi possível alterar a senha."));
    }
  }

  return (
    <form className="card mt-3" onSubmit={submit}>
      <div className="card-header">
        <h3 className="card-title">
          <IconLock size={18} className="me-2" />
          Alterar senha
        </h3>
      </div>
      <div className="card-body">
        {error && <div className="alert alert-danger">{error}</div>}
        {saved && <div className="alert alert-success">Senha alterada.</div>}
        <div className="row g-3">
          <div className="col-md-4">
            <label className="form-label required">Senha atual</label>
            <input
              type="password"
              className="form-control"
              value={form.current}
              onChange={(e) => set("current", e.target.value)}
              autoComplete="current-password"
            />
          </div>
          <div className="col-md-4">
            <label className="form-label required">Nova senha</label>
            <input
              type="password"
              className={`form-control${tooShort ? " is-invalid" : ""}`}
              value={form.next}
              onChange={(e) => set("next", e.target.value)}
              autoComplete="new-password"
            />
            {tooShort && <div className="invalid-feedback">Use pelo menos 8 caracteres.</div>}
          </div>
          <div className="col-md-4">
            <label className="form-label required">Confirmar nova senha</label>
            <input
              type="password"
              className={`form-control${mismatch ? " is-invalid" : ""}`}
              value={form.confirm}
              onChange={(e) => set("confirm", e.target.value)}
              autoComplete="new-password"
            />
            {mismatch && <div className="invalid-feedback">As senhas não conferem.</div>}
          </div>
        </div>
      </div>
      <div className="card-footer text-end">
        <button type="submit" className="btn btn-primary" disabled={invalid || change.isPending}>
          {change.isPending ? "Alterando…" : "Alterar senha"}
        </button>
      </div>
    </form>
  );
}

const quandoDe = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

/** Crédito do usuário — sempre visível, para o saldo zero não virar dúvida. */
function CreditCard() {
  const { data, isLoading } = useCredits();
  if (isLoading || !data) return null;
  const vazio = data.entries.length === 0;

  return (
    <div className="card mt-3">
      <div className="card-header d-flex align-items-center gap-2">
        <IconWallet size={20} />
        <h3 className="card-title m-0">Meu crédito</h3>
        <span className="credit-balance ms-auto">R$ {brl(data.balance)}</span>
      </div>
      <div className="card-body pb-0">
        <p className="text-secondary">
          {vazio
            ? "Você não tem crédito. Se cancelar um horário já pago, o valor volta para cá e paga o próximo corte."
            : "Crédito de horário cancelado. Ele paga o próximo corte avulso automaticamente, sem precisar de Pix."}
        </p>
      </div>
      {!vazio && (
      <div className="table-responsive">
        <table className="table table-vcenter card-table">
          <thead>
            <tr>
              <th>Quando</th>
              <th>Movimento</th>
              <th className="text-end">Valor</th>
            </tr>
          </thead>
          <tbody>
            {data.entries.map((e) => {
              const valor = Number(e.amount);
              return (
                <tr key={e.id}>
                  <td className="text-nowrap">{quandoDe(e.created_at)}</td>
                  <td>
                    <div>{e.reason_label}</div>
                    {e.note && <div className="text-secondary small">{e.note}</div>}
                  </td>
                  <td className={`text-end asset-tag ${valor >= 0 ? "text-green" : "text-secondary"}`}>
                    {valor >= 0 ? "+" : "−"} R$ {brl(Math.abs(valor))}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      )}
    </div>
  );
}

/** Situação da mensalidade — só aparece pra quem está na relação financeira. */
function FinanceCard() {
  const { data, isLoading } = useMyFinance();
  if (isLoading || !data) return null;

  return (
    <div className="card mt-3">
      <div className="card-header d-flex align-items-center gap-2">
        <IconReceipt2 size={20} />
        <h3 className="card-title m-0">Minha mensalidade</h3>
        <span className={`badge ms-auto ${FINANCIAL_STATUS_BADGE[data.financial_status]}`}>
          {FINANCIAL_STATUS_LABEL[data.financial_status]}
        </span>
      </div>
      <div className="card-body">
        <div className="datagrid">
          <div className="datagrid-item">
            <div className="datagrid-title">Próximo vencimento</div>
            <div className="datagrid-content">
              {data.next_due_date ? formatDateBr(data.next_due_date) : "—"}
            </div>
          </div>
          <div className="datagrid-item">
            <div className="datagrid-title">Meses pagos</div>
            <div className="datagrid-content">{data.months_paid}</div>
          </div>
          <div className="datagrid-item">
            <div className="datagrid-title">Meses em aberto</div>
            <div className="datagrid-content">{data.months_open}</div>
          </div>
          <div className="datagrid-item">
            <div className="datagrid-title">Valor pendente</div>
            <div className="datagrid-content">R$ {brl(data.pending_amount)}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ProfilePage() {
  const { user } = useAuth();
  if (!user) return null;

  const roles = user.roles.map((r) => ROLE_LABEL[r] ?? r).join(", ");
  const initials = (user.nome_guerra || user.full_name || user.username || "?")
    .split(/\s+/)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <>
      <div className="page-header d-print-none mb-3">
        <div className="row align-items-center">
          <div className="col">
            <h2 className="page-title">
              <IconUser size={22} className="me-2" />
              Meu perfil
            </h2>
            <div className="text-secondary mt-1">{ORG_NAME}</div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-body">
          <div className="d-flex align-items-center gap-3 mb-4">
            <span className="avatar avatar-lg bg-primary text-white">{initials}</span>
            <div className="lh-sm">
              <div className="h3 mb-1">{user.display_name || user.username}</div>
              <div className="text-secondary">{roles || "Usuário"}</div>
            </div>
          </div>

          <div className="datagrid">
            <Field label="Nome completo" value={user.full_name ?? ""} />
            <Field label="CPF" value={user.cpf ? maskCpf(user.cpf) : ""} />
            <Field label="Data de nascimento" value={formatDateBr(user.birth_date)} />
            <Field label="Cadastrado em" value={formatDateBr(user.date_joined)} />
          </div>
        </div>
        <div className="card-footer text-secondary small">
          Nome completo, CPF e data de nascimento são mantidos pelo administrador.
        </div>
      </div>

      <CreditCard />
      <FinanceCard />

      <div className="mt-3">
        <ProfileForm />
      </div>
      <PasswordForm />
    </>
  );
}
