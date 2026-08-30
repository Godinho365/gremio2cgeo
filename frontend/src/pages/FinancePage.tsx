import { IconBuildingBank, IconPlus } from "@tabler/icons-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { brl } from "../features/barbershop/api";
import {
  eligiblePlansFor,
  FINANCIAL_STATUS_BADGE,
  FINANCIAL_STATUS_LABEL,
  PLAN_LABEL,
  useActivateBilling,
  useBillingProfiles,
  useFinanceDashboard,
  useGenerateInvite,
  usePendingInvites,
  type PlanCode,
} from "../features/finance/api";
import { useUsers } from "../features/accounts/api";
import { useAuth } from "../auth/AuthContext";
import { isAdmin } from "../auth/roles";

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="col-sm-6 col-lg-3">
      <div className="card card-sm">
        <div className="card-body">
          <div className="text-secondary small">{label}</div>
          <div className="h2 mb-0">{value}</div>
        </div>
      </div>
    </div>
  );
}

function ActivateBillingModal({ onClose }: { onClose: () => void }) {
  const { data: users } = useUsers();
  const { data: profiles } = useBillingProfiles();
  const activate = useActivateBilling();
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    user: "",
    plan: "" as PlanCode | "",
    due_day: 10,
    started_period: today.slice(0, 8) + "01",
  });
  const [error, setError] = useState<string | null>(null);

  // Quem já está na relação (ativa ou não) não aparece de novo — reativar
  // exige editar o cadastro existente, não criar um segundo.
  const billedIds = new Set((profiles ?? []).map((p) => p.user));
  const candidatos = (users ?? []).filter(
    (u) => eligiblePlansFor(u.posto_graduacao).length > 0 && !billedIds.has(u.id),
  );

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!form.plan) return;
    try {
      await activate.mutateAsync({ ...form, plan: form.plan });
      onClose();
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response?.data
        ?.error?.message;
      setError(msg ?? "Não foi possível ativar a cobrança.");
    }
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Ativar cobrança</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                {error && <div className="alert alert-danger">{error}</div>}
                <div className="mb-3">
                  <label className="form-label required">Usuário</label>
                  <select
                    className="form-select"
                    value={form.user}
                    onChange={(e) => setForm((f) => ({ ...f, user: e.target.value }))}
                    required
                  >
                    <option value="">Selecione…</option>
                    {candidatos.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.display_name || u.username}
                      </option>
                    ))}
                  </select>
                  <div className="form-hint">Só aparecem usuários com posto elegível a algum plano.</div>
                </div>
                {form.user && (
                  <div className="mb-3">
                    <label className="form-label required">Plano</label>
                    <select
                      className="form-select"
                      value={form.plan}
                      onChange={(e) => setForm((f) => ({ ...f, plan: e.target.value as PlanCode }))}
                      required
                    >
                      <option value="">Selecione…</option>
                      {eligiblePlansFor(
                        candidatos.find((u) => u.id === form.user)?.posto_graduacao ?? "",
                      ).map((code) => (
                        <option key={code} value={code}>
                          {PLAN_LABEL[code]}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                <div className="row">
                  <div className="col-6 mb-3">
                    <label className="form-label required">Dia de vencimento</label>
                    <input
                      type="number"
                      className="form-control"
                      min={1}
                      max={31}
                      value={form.due_day}
                      onChange={(e) => setForm((f) => ({ ...f, due_day: Number(e.target.value) }))}
                      required
                    />
                  </div>
                  <div className="col-6 mb-3">
                    <label className="form-label required">Mês de início</label>
                    <input
                      type="date"
                      className="form-control"
                      value={form.started_period}
                      onChange={(e) => setForm((f) => ({ ...f, started_period: e.target.value }))}
                      required
                    />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={activate.isPending || !form.plan}>
                  {activate.isPending ? "Ativando…" : "Ativar"}
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

export default function FinancePage() {
  const { data: dashboard } = useFinanceDashboard();
  const { data: profiles, isLoading: profilesLoading } = useBillingProfiles();
  const { data: users, isLoading: usersLoading } = useUsers();
  const [activating, setActivating] = useState(false);
  const { user } = useAuth();
  const canManage = isAdmin(user);
  const isLoading = profilesLoading || usersLoading;

  // Todo usuário ativo aparece aqui — com ou sem plano — não só quem já
  // tem BillingProfile. Quem não tem plano mostra "Inativo".
  const profileByUser = new Map((profiles ?? []).map((p) => [p.user, p]));
  const rows = (users ?? [])
    .filter((u) => u.is_active)
    .map((u) => ({ user: u, profile: profileByUser.get(u.id) }))
    .sort((a, b) => (a.user.display_name || a.user.username).localeCompare(
      b.user.display_name || b.user.username,
    ));

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <div className="page-pretitle">Módulo</div>
            <h2 className="page-title">
              <IconBuildingBank size={22} className="me-2" />
              Sistema Financeiro
            </h2>
          </div>
          {canManage && (
            <div className="col-auto">
              <button className="btn btn-primary" onClick={() => setActivating(true)}>
                <IconPlus size={18} className="me-1" />
                Ativar cobrança
              </button>
            </div>
          )}
        </div>
      </div>

      {dashboard && (
        <div className="row row-cards mt-3 g-3">
          <StatCard label="Usuários na relação" value={dashboard.total_users} />
          <StatCard label="Em dia" value={dashboard.up_to_date_count} />
          <StatCard label="Inadimplentes" value={dashboard.delinquent_count} />
          <StatCard label="Vencidas" value={dashboard.dues_overdue} />
          <StatCard label="A vencer (30 dias)" value={dashboard.dues_upcoming_30_days} />
          <StatCard label="Valores em aberto" value={`R$ ${brl(dashboard.pending_amount)}`} />
          <StatCard label="Crédito em aberto" value={`R$ ${brl(dashboard.advance_payments_received)}`} />
          <StatCard label="Previsão a receber" value={`R$ ${brl(dashboard.upcoming_receivable)}`} />
        </div>
      )}

      <div className="card mt-3">
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th>Usuário</th>
                <th>Posto/Grad.</th>
                <th>Plano</th>
                <th>Situação</th>
                <th>Vencimento</th>
                <th className="w-1" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={6} className="text-secondary">Carregando…</td>
                </tr>
              )}
              {!isLoading && rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-secondary text-center py-4">
                    Nenhum usuário cadastrado.
                  </td>
                </tr>
              )}
              {rows.map(({ user: u, profile: p }) => (
                <tr key={u.id}>
                  <td>{u.display_name || u.username}</td>
                  <td>{u.posto_graduacao || "—"}</td>
                  <td>{p?.plan_label ?? "—"}</td>
                  <td>
                    {p ? (
                      <>
                        <span className={`badge ${FINANCIAL_STATUS_BADGE[p.financial_status]}`}>
                          {FINANCIAL_STATUS_LABEL[p.financial_status]}
                        </span>
                        {!p.is_active && <span className="badge bg-secondary-lt ms-1">Desativado</span>}
                      </>
                    ) : (
                      <span className="badge bg-secondary-lt">Inativo</span>
                    )}
                  </td>
                  <td>{p ? `Dia ${p.due_day}` : "—"}</td>
                  <td>
                    {p && (
                      <Link to={`/financeiro/${p.id}`} className="btn btn-sm btn-ghost-secondary">
                        Ver extrato
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {canManage && <AssociadoInvites />}

      {activating && <ActivateBillingModal onClose={() => setActivating(false)} />}
    </>
  );
}

function AssociadoInvites() {
  const { data: invites } = usePendingInvites();
  const { data: users } = useUsers();
  const { data: profiles } = useBillingProfiles();
  const generate = useGenerateInvite();
  const [link, setLink] = useState<string | null>(null);

  const billedIds = new Set((profiles ?? []).map((p) => p.user));
  const invitedIds = new Set((invites ?? []).filter((i) => !i.used_at).map((i) => i.user));
  const candidatos = (users ?? []).filter(
    (u) =>
      eligiblePlansFor(u.posto_graduacao).length === 2 &&
      !billedIds.has(u.id) &&
      !invitedIds.has(u.id),
  );

  return (
    <div className="card mt-3">
      <div className="card-header">
        <h3 className="card-title">Convite para o Associado Full</h3>
      </div>
      <div className="card-body">
        {link && (
          <div className="alert alert-success">
            Link gerado: <code>{link}</code>
          </div>
        )}
        <p className="text-secondary">
          Cabos e Soldados EP podem escolher entre Associado Full e Assinatura
          Barbearia. Gere um convite pra deixar a pessoa escolher ela mesma.
        </p>
        <select
          className="form-select mb-2"
          defaultValue=""
          onChange={async (e) => {
            if (!e.target.value) return;
            const invite = await generate.mutateAsync(e.target.value);
            setLink(`${window.location.origin}/convite/associado/${invite.token}`);
            e.target.value = "";
          }}
        >
          <option value="">Gerar convite para…</option>
          {candidatos.map((u) => (
            <option key={u.id} value={u.id}>
              {u.display_name || u.username}
            </option>
          ))}
        </select>
        {(invites ?? []).filter((i) => !i.used_at).length > 0 && (
          <table className="table table-sm mt-2">
            <tbody>
              {(invites ?? [])
                .filter((i) => !i.used_at)
                .map((i) => (
                  <tr key={i.id}>
                    <td>{i.user_name}</td>
                    <td className="text-secondary small">
                      expira {new Date(i.expires_at).toLocaleDateString("pt-BR")}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
