import { IconArrowLeft, IconCash } from "@tabler/icons-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { brl } from "../features/barbershop/api";
import {
  FINANCIAL_STATUS_BADGE,
  useActivateBilling,
  useBillingProfiles,
  useCancelPayment,
  useDeactivateBilling,
  useDues,
  useRegisterPayment,
  type RegisterPaymentPayload,
} from "../features/finance/api";
import { formatDateBr } from "../lib/masks";
import { useAuth } from "../auth/AuthContext";
import { isAdmin } from "../auth/roles";

function periodLabel(iso: string): string {
  const [year, month] = iso.split("-");
  return new Date(Number(year), Number(month) - 1, 1).toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
  });
}

function RegisterPaymentModal({
  userId,
  feeHint,
  onClose,
}: {
  userId: string;
  /** Valor de uma mensalidade, pra pré-visualizar quantos meses o pagamento cobre.
   *  Vem da Due mais recente por período (nunca hardcoded — MEMBERSHIP_FEE pode
   *  mudar; a Due já gerada carrega o valor real daquele mês). `dues` vem ordenado
   *  ASCENDENTE por period (ver DueViewSet.get_queryset / Due.Meta.ordering), então
   *  a mais recente é o ÚLTIMO elemento, não o primeiro. */
  feeHint: number;
  onClose: () => void;
}) {
  const register = useRegisterPayment();
  const [form, setForm] = useState<RegisterPaymentPayload>({
    user: userId,
    amount: "",
    method: "dinheiro",
    paid_at: new Date().toISOString().slice(0, 16),
  });
  const [error, setError] = useState<string | null>(null);

  const meses =
    Number(form.amount) > 0 && feeHint > 0 ? Math.floor(Number(form.amount) / feeHint) : 0;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await register.mutateAsync({ ...form, paid_at: new Date(form.paid_at).toISOString() });
      onClose();
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response?.data
        ?.error?.message;
      setError(msg ?? "Não foi possível registrar o pagamento.");
    }
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Registrar pagamento</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                {error && <div className="alert alert-danger">{error}</div>}
                <div className="row">
                  <div className="col-6 mb-3">
                    <label className="form-label required">Valor</label>
                    <input
                      type="number"
                      step="0.01"
                      className="form-control"
                      value={form.amount}
                      onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
                      required
                    />
                  </div>
                  <div className="col-6 mb-3">
                    <label className="form-label required">Forma</label>
                    <select
                      className="form-select"
                      value={form.method}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, method: e.target.value as RegisterPaymentPayload["method"] }))
                      }
                    >
                      <option value="dinheiro">Dinheiro</option>
                      <option value="transferencia">Transferência</option>
                      <option value="pix">Pix (manual)</option>
                    </select>
                  </div>
                </div>
                <div className="mb-3">
                  <label className="form-label required">Data do pagamento</label>
                  <input
                    type="datetime-local"
                    className="form-control"
                    value={form.paid_at}
                    onChange={(e) => setForm((f) => ({ ...f, paid_at: e.target.value }))}
                    required
                  />
                </div>
                {meses > 0 && (
                  <div className="alert alert-info mb-0">
                    Esse valor cobre {meses} {meses === 1 ? "mês" : "meses"} de mensalidade.
                  </div>
                )}
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={register.isPending}>
                  {register.isPending ? "Registrando…" : "Registrar"}
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

export default function FinanceStatementPage() {
  const { id = "" } = useParams();
  const { data: profiles } = useBillingProfiles();
  const profile = (profiles ?? []).find((p) => p.id === id);
  const { data: dues, isLoading } = useDues({ billing_profile: id });
  const cancel = useCancelPayment();
  const deactivate = useDeactivateBilling();
  const { user } = useAuth();
  const canManage = isAdmin(user);
  const activate = useActivateBilling();
  const [registering, setRegistering] = useState(false);

  if (!profile) return null;

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <Link to="/financeiro" className="text-secondary text-decoration-none small mb-1 d-block">
              <IconArrowLeft size={14} className="me-1" />
              Financeiro
            </Link>
            <h2 className="page-title">{profile.user_name}</h2>
            <div className="text-secondary mt-1">
              <span className={`badge ${FINANCIAL_STATUS_BADGE[profile.financial_status]}`}>
                {profile.financial_status_label}
              </span>
            </div>
          </div>
          <div className="col-auto d-flex gap-2">
            {canManage && profile.is_active && (
              <button
                className="btn btn-outline-danger"
                onClick={() => {
                  if (confirm(`Desativar a cobrança de ${profile.user_name}?`)) deactivate.mutate(profile.id);
                }}
              >
                Desativar cobrança
              </button>
            )}
            {canManage && !profile.is_active && (
              <button
                className="btn btn-outline-success"
                onClick={() => {
                  if (confirm(`Reativar a cobrança de ${profile.user_name}?`))
                    activate.mutate({
                      user: profile.user,
                      plan: profile.plan,
                      due_day: profile.due_day,
                      started_period: profile.started_period,
                    });
                }}
              >
                Reativar cobrança
              </button>
            )}
            {canManage && (
              <button className="btn btn-primary" onClick={() => setRegistering(true)}>
                <IconCash size={18} className="me-1" />
                Registrar pagamento
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="card mt-3">
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th>Período</th>
                <th>Vencimento</th>
                <th>Valor</th>
                <th>Situação</th>
                <th className="w-1" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={5} className="text-secondary">Carregando…</td>
                </tr>
              )}
              {(dues ?? []).map((due) => (
                <tr key={due.id}>
                  <td className="text-capitalize">{periodLabel(due.period)}</td>
                  <td>{formatDateBr(due.due_date)}</td>
                  <td>R$ {brl(due.amount)}</td>
                  <td>
                    {due.status_label}
                    {due.paid_in_advance && (
                      <span className="badge bg-blue-lt ms-1">Antecipado</span>
                    )}
                  </td>
                  <td>
                    {canManage && due.status === "paid" && (
                      <button
                        className="btn btn-sm btn-ghost-danger"
                        onClick={() => {
                          if (confirm("Cancelar este pagamento? A mensalidade volta a ficar em aberto."))
                            cancel.mutate(due.id);
                        }}
                      >
                        Cancelar pagamento
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {registering && (
        <RegisterPaymentModal
          userId={profile.user}
          feeHint={Number((dues ?? []).at(-1)?.amount ?? 0)}
          onClose={() => setRegistering(false)}
        />
      )}
    </>
  );
}
