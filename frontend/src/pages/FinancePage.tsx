import { IconBuildingBank, IconDownload, IconPlus } from "@tabler/icons-react";
import { useMemo, useState } from "react";
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
  useFinanceMonthlyReport,
  useGenerateInvite,
  usePendingInvites,
  type MonthlyReportRow,
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

const ANO_ATUAL = new Date().getFullYear();
const YEAR_OPTIONS = [0, 1, 2, 3, 4].map((n) => ANO_ATUAL - n);

function mesLabel(periodIso: string): string {
  const [ano, mes] = periodIso.split("-").map(Number);
  return new Date(ano, mes - 1, 1)
    .toLocaleDateString("pt-BR", { month: "short", year: "2-digit" })
    .replace(".", "");
}

/** Barras agrupadas (arrecadado x em aberto) por mês — sem lib de gráfico,
 * só SVG: é a única coisa que precisa desse tipo de visual no projeto. */
function MonthlyBarChart({ rows }: { rows: MonthlyReportRow[] }) {
  const width = 720;
  const height = 220;
  const padding = { top: 12, bottom: 34 };
  const plotHeight = height - padding.top - padding.bottom;
  const max = Math.max(
    1,
    ...rows.flatMap((r) => [Number(r.dues_paid_amount), Number(r.dues_open_amount)]),
  );
  const groupWidth = width / Math.max(1, rows.length);
  const barWidth = Math.min(24, groupWidth / 3);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-100"
      role="img"
      aria-label="Comparativo mensal: arrecadado versus em aberto"
    >
      {rows.map((r, i) => {
        const cx = groupWidth * i + groupWidth / 2;
        const recebido = Number(r.dues_paid_amount);
        const aberto = Number(r.dues_open_amount);
        const hRecebido = (recebido / max) * plotHeight;
        const hAberto = (aberto / max) * plotHeight;
        return (
          <g key={r.period}>
            <rect
              x={cx - barWidth - 2}
              y={padding.top + plotHeight - hRecebido}
              width={barWidth}
              height={hRecebido}
              fill="var(--tblr-green)"
              rx="2"
            >
              <title>{`Arrecadado referente a ${mesLabel(r.period)}: R$ ${brl(r.dues_paid_amount)}`}</title>
            </rect>
            <rect
              x={cx + 2}
              y={padding.top + plotHeight - hAberto}
              width={barWidth}
              height={hAberto}
              fill="var(--tblr-red)"
              rx="2"
            >
              <title>{`Em aberto em ${mesLabel(r.period)}: R$ ${brl(r.dues_open_amount)}`}</title>
            </rect>
            <text
              x={cx}
              y={height - 12}
              textAnchor="middle"
              fontSize="11"
              fill="var(--tblr-body-color)"
            >
              {mesLabel(r.period)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function exportarRelatorioMensalCsv(rows: MonthlyReportRow[]) {
  const cabecalho = [
    "Mês",
    "Mensalidades geradas",
    "Pagas (qtd)",
    "Arrecadado (R$)",
    "Variação vs mês anterior (%)",
    "Taxa de inadimplência (%)",
    "Em aberto (qtd)",
    "Valor em aberto (R$)",
    "Associado Full pago (R$)",
    "Assinatura Barbearia pago (R$)",
  ];
  const linhas = rows.map((r) => [
    r.period,
    String(r.dues_total_count),
    String(r.dues_paid_count),
    r.dues_paid_amount,
    r.revenue_change_pct == null ? "" : r.revenue_change_pct.toFixed(1),
    (Number(r.delinquency_rate) * 100).toFixed(1),
    String(r.dues_open_count),
    r.dues_open_amount,
    r.by_plan.associado?.paid_amount ?? "0.00",
    r.by_plan.barbearia?.paid_amount ?? "0.00",
  ]);
  const csv = [cabecalho, ...linhas].map((cols) => cols.join(";")).join("\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `financeiro-mensal-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function VariacaoBadge({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-secondary">—</span>;
  const positivo = pct > 0;
  const zero = pct === 0;
  return (
    <span className={zero ? "text-secondary" : positivo ? "text-green" : "text-red"}>
      {positivo ? "▲" : zero ? "" : "▼"} {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

/** Detalhe de um mês selecionado: quebra por plano (Associado Full x
 * Assinatura Barbearia) — só aparece quando alguém clica numa linha. */
function MonthlyDetail({ row, onClose }: { row: MonthlyReportRow; onClose: () => void }) {
  return (
    <div className="card-body border-top">
      <div className="d-flex align-items-center justify-content-between mb-2">
        <h4 className="m-0">Detalhe — {mesLabel(row.period)}</h4>
        <button type="button" className="btn btn-sm btn-ghost-secondary" onClick={onClose}>
          Fechar
        </button>
      </div>
      <div className="table-responsive">
        <table className="table table-sm table-vcenter">
          <thead>
            <tr>
              <th>Plano</th>
              <th className="text-end">Pagas</th>
              <th className="text-end">Arrecadado</th>
              <th className="text-end">Em aberto</th>
              <th className="text-end">Valor em aberto</th>
            </tr>
          </thead>
          <tbody>
            {(["associado", "barbearia"] as const).map((plan) => {
              const b = row.by_plan[plan];
              return (
                <tr key={plan}>
                  <td>{PLAN_LABEL[plan]}</td>
                  <td className="text-end">{b?.paid_count ?? 0}</td>
                  <td className="text-end">R$ {brl(b?.paid_amount ?? "0.00")}</td>
                  <td className="text-end">{b?.open_count ?? 0}</td>
                  <td className="text-end">R$ {brl(b?.open_amount ?? "0.00")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Comparativo por ano civil: arrecadação e situação das mensalidades de
 * cada mês — gráfico, indicadores, tabela clicável e exportação CSV. */
function MonthlyReportSection() {
  const [year, setYear] = useState(ANO_ATUAL);
  const [selectedPeriod, setSelectedPeriod] = useState<string | null>(null);
  const { data: rows, isLoading } = useFinanceMonthlyReport(year);

  const resumo = useMemo(() => {
    if (!rows || rows.length === 0) return null;
    const somaPago = rows.reduce((s, r) => s + Number(r.dues_paid_amount), 0);
    const somaAberto = rows.reduce((s, r) => s + Number(r.dues_open_amount), 0);
    const somaTotal = rows.reduce((s, r) => s + Number(r.dues_total_amount), 0);
    const somaGeradas = rows.reduce((s, r) => s + r.dues_total_count, 0);
    return {
      pago: somaPago,
      aberto: somaAberto,
      geradas: somaGeradas,
      inadimplenciaMedia: somaTotal > 0 ? (somaAberto / somaTotal) * 100 : 0,
    };
  }, [rows]);

  const selectedRow = rows?.find((r) => r.period === selectedPeriod) ?? null;

  return (
    <div className="card mt-3">
      <div className="card-header">
        <h3 className="card-title">Comparativo mensal</h3>
        <div className="card-actions d-flex align-items-center gap-2">
          <select
            className="form-select form-select-sm w-auto"
            value={year}
            onChange={(e) => {
              setYear(Number(e.target.value));
              setSelectedPeriod(null);
            }}
          >
            {YEAR_OPTIONS.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary"
            disabled={!rows || rows.length === 0}
            onClick={() => rows && exportarRelatorioMensalCsv(rows)}
          >
            <IconDownload size={16} className="me-1" />
            Exportar CSV
          </button>
        </div>
      </div>

      {resumo && (
        <div className="row row-cards g-3 p-3 pb-0">
          <StatCard label={`Arrecadado em ${year}`} value={`R$ ${brl(resumo.pago)}`} />
          <StatCard label={`Em aberto em ${year}`} value={`R$ ${brl(resumo.aberto)}`} />
          <StatCard
            label="Taxa de inadimplência média"
            value={`${resumo.inadimplenciaMedia.toFixed(1)}%`}
          />
          <StatCard label="Mensalidades geradas no ano" value={resumo.geradas} />
        </div>
      )}

      <div className="card-body">
        {isLoading && <div className="text-secondary">Carregando…</div>}
        {rows && rows.length > 0 && (
          <>
            <MonthlyBarChart rows={rows} />
            <div className="d-flex gap-3 mt-1 mb-3 small text-secondary">
              <span>
                <span
                  className="d-inline-block rounded-1 me-1"
                  style={{ width: 10, height: 10, background: "var(--tblr-green)" }}
                />
                Arrecadado
              </span>
              <span>
                <span
                  className="d-inline-block rounded-1 me-1"
                  style={{ width: 10, height: 10, background: "var(--tblr-red)" }}
                />
                Em aberto
              </span>
              <span className="ms-auto">Clique numa linha da tabela pra ver a quebra por plano.</span>
            </div>
          </>
        )}
      </div>
      {rows && rows.length > 0 && (
        <div className="table-responsive">
          <table className="table table-vcenter card-table table-hover">
            <thead>
              <tr>
                <th>Mês</th>
                <th className="text-end">Mensalidades</th>
                <th className="text-end">Pagas</th>
                <th className="text-end">Arrecadado</th>
                <th className="text-end">Δ mês anterior</th>
                <th className="text-end">Inadimplência</th>
                <th className="text-end">Em aberto</th>
                <th className="text-end">Valor em aberto</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.period}
                  role="button"
                  className={r.period === selectedPeriod ? "table-active" : ""}
                  onClick={() => setSelectedPeriod(r.period === selectedPeriod ? null : r.period)}
                >
                  <td>{mesLabel(r.period)}</td>
                  <td className="text-end">{r.dues_total_count}</td>
                  <td className="text-end">{r.dues_paid_count}</td>
                  <td className="text-end">R$ {brl(r.dues_paid_amount)}</td>
                  <td className="text-end">
                    <VariacaoBadge pct={r.revenue_change_pct} />
                  </td>
                  <td className="text-end">{(Number(r.delinquency_rate) * 100).toFixed(1)}%</td>
                  <td className="text-end">{r.dues_open_count}</td>
                  <td className="text-end">R$ {brl(r.dues_open_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {selectedRow && <MonthlyDetail row={selectedRow} onClose={() => setSelectedPeriod(null)} />}
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
                <div className="mb-3">
                  <label className="form-label required">Mês de início</label>
                  <input
                    type="date"
                    className="form-control"
                    value={form.started_period}
                    onChange={(e) => setForm((f) => ({ ...f, started_period: e.target.value }))}
                    required
                  />
                  <div className="form-hint">Vencimento é sempre dia 5.</div>
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

      <MonthlyReportSection />

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
