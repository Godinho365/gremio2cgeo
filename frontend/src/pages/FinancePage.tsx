import { IconBuildingBank, IconPlus } from "@tabler/icons-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { brl } from "../features/barbershop/api";
import {
  FINANCIAL_STATUS_BADGE,
  FINANCIAL_STATUS_LABEL,
  useActivateBilling,
  useBillingProfiles,
  useFinanceDashboard,
  type BillingProfile,
} from "../features/finance/api";
import { useUsers } from "../features/accounts/api";

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
  const [form, setForm] = useState({ user: "", due_day: 10, started_period: today.slice(0, 8) + "01" });
  const [error, setError] = useState<string | null>(null);

  // Quem já está na relação (ativa ou não) não aparece de novo — reativar
  // exige editar o cadastro existente, não criar um segundo.
  const billedIds = new Set((profiles ?? []).map((p) => p.user));
  const candidatos = (users ?? []).filter(
    (u) => u.posto_graduacao !== "Sd" && u.posto_graduacao !== "Cb" && !billedIds.has(u.id),
  );

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await activate.mutateAsync(form);
      onClose();
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response?.data
        ?.error?.message;
      setError(msg ?? "Não foi possível ativar a cobrança.");
    }
  }

  return (
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
                <div className="form-hint">Praças (Sd/Cb) não aparecem — não entram na relação.</div>
              </div>
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
              <button type="submit" className="btn btn-primary" disabled={activate.isPending}>
                {activate.isPending ? "Ativando…" : "Ativar"}
              </button>
            </div>
          </form>
        </div>
      </div>
      <div className="modal-backdrop fade show" />
    </div>
  );
}

export default function FinancePage() {
  const { data: dashboard } = useFinanceDashboard();
  const { data: profiles, isLoading } = useBillingProfiles();
  const [activating, setActivating] = useState(false);

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
          <div className="col-auto">
            <button className="btn btn-primary" onClick={() => setActivating(true)}>
              <IconPlus size={18} className="me-1" />
              Ativar cobrança
            </button>
          </div>
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
          <StatCard label="Recebido antecipado" value={`R$ ${brl(dashboard.advance_payments_received)}`} />
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
                <th>Situação</th>
                <th>Vencimento</th>
                <th className="w-1" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={5} className="text-secondary">Carregando…</td>
                </tr>
              )}
              {!isLoading && (profiles ?? []).length === 0 && (
                <tr>
                  <td colSpan={5} className="text-secondary text-center py-4">
                    Nenhum usuário na relação financeira ainda.
                  </td>
                </tr>
              )}
              {(profiles ?? []).map((p: BillingProfile) => (
                <tr key={p.id}>
                  <td>{p.user_name}</td>
                  <td>{p.user_posto || "—"}</td>
                  <td>
                    <span className={`badge ${FINANCIAL_STATUS_BADGE[p.financial_status]}`}>
                      {FINANCIAL_STATUS_LABEL[p.financial_status]}
                    </span>
                    {!p.is_active && <span className="badge bg-secondary-lt ms-1">Desativado</span>}
                  </td>
                  <td>Dia {p.due_day}</td>
                  <td>
                    <Link to={`/financeiro/${p.id}`} className="btn btn-sm btn-ghost-secondary">
                      Ver extrato
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {activating && <ActivateBillingModal onClose={() => setActivating(false)} />}
    </>
  );
}
