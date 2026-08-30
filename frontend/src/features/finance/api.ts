import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";
import type { Payment } from "../barbershop/api";

export type FinancialStatus =
  | "up_to_date"
  | "paid_in_advance"
  | "due_soon"
  | "due_today"
  | "overdue"
  | "delinquent";

// Pago antecipadamente conta como em dia — quem pagou mais meses do que
// devia está tão em dia quanto quem pagou exatamente o mês corrente, só
// que mais confortável. Mesmo rótulo/cor de up_to_date de propósito.
export const FINANCIAL_STATUS_LABEL: Record<FinancialStatus, string> = {
  up_to_date: "Em dia",
  paid_in_advance: "Em dia",
  due_soon: "Próximo do vencimento",
  due_today: "Vencendo hoje",
  overdue: "Vencido",
  delinquent: "Inadimplente",
};

/** Classe de badge (Tabler) por situação — verde a vermelho conforme piora. */
export const FINANCIAL_STATUS_BADGE: Record<FinancialStatus, string> = {
  up_to_date: "bg-green-lt",
  paid_in_advance: "bg-green-lt",
  due_soon: "bg-yellow-lt",
  due_today: "bg-orange-lt",
  overdue: "bg-red-lt",
  delinquent: "bg-red-lt",
};

export type PlanCode = "associado" | "barbearia";

export const PLAN_LABEL: Record<PlanCode, string> = {
  associado: "Associado Full",
  barbearia: "Assinatura Barbearia",
};

const _BARBEARIA_ONLY: readonly string[] = ["Sd EV"];
const _BOTH_PLANS: readonly string[] = ["Sd EP", "Cb"];
const _UNCLASSIFIED: readonly string[] = ["Sd", ""];

/** Espelha `eligible_plans_for` do backend — só pra filtrar a UI; a regra
 * de verdade é sempre validada no servidor. */
export function eligiblePlansFor(posto: string): PlanCode[] {
  if (_UNCLASSIFIED.includes(posto)) return [];
  if (_BARBEARIA_ONLY.includes(posto)) return ["barbearia"];
  if (_BOTH_PLANS.includes(posto)) return ["associado", "barbearia"];
  return ["associado"];
}

/** Mesmos planos de `eligiblePlansFor`, exceto o Associado Full pra Cb/Sd EP
 * — eles precisam de convite (do administrador ou de outro Associado Full em
 * dia) pra esse plano específico; `FinanceService.self_subscribe` recusa a
 * ativação direta no servidor. Só usado pra decidir os botões de
 * autoatendimento no perfil. */
export function selfServicePlansFor(posto: string): PlanCode[] {
  if (_BOTH_PLANS.includes(posto)) return ["barbearia"];
  return eligiblePlansFor(posto);
}

export interface BillingProfile {
  id: string;
  user: string;
  user_name: string;
  user_posto: string;
  plan: PlanCode;
  plan_label: string;
  due_day: number;
  started_period: string;
  is_active: boolean;
  financial_status: FinancialStatus;
  financial_status_label: string;
  last_payment_at: string | null;
}

export type DueStatus =
  | "pending"
  | "due_soon"
  | "due_today"
  | "overdue"
  | "delinquent"
  | "paid";

export interface Due {
  id: string;
  billing_profile: string;
  user: string;
  user_name: string;
  period: string;
  due_date: string;
  amount: string;
  status: DueStatus;
  status_label: string;
  paid_in_advance: boolean;
  paid_at: string | null;
}

/** "agosto de 2026" a partir de um period ISO ("2026-08-01"). */
export function periodLabel(iso: string): string {
  const [year, month] = iso.split("-");
  return new Date(Number(year), Number(month) - 1, 1).toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
  });
}

interface Paginated<T> {
  results: T[];
  count: number;
}

export function useBillingProfiles() {
  return useQuery({
    queryKey: ["finance", "billing-profiles"],
    queryFn: async () =>
      (await api.get<Paginated<BillingProfile>>("/billing-profiles?page_size=200")).data.results,
  });
}

export interface ActivateBillingPayload {
  user: string;
  plan: PlanCode;
  started_period: string;
}

export function useActivateBilling() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ActivateBillingPayload) =>
      (await api.post<BillingProfile>("/billing-profiles", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

export interface AssociadoInvite {
  id: string;
  user: string;
  user_name: string;
  token: string;
  expires_at: string;
  used_at: string | null;
  created_at: string;
}

export function usePendingInvites() {
  return useQuery({
    queryKey: ["finance", "invites"],
    queryFn: async () =>
      (await api.get<AssociadoInvite[]>("/finance/convites-associado")).data,
  });
}

export interface InviteCandidate {
  id: string;
  display_name: string;
  posto_graduacao: string;
}

/** Busca limitada de candidatos ao convite — quem convida sem ser Admin não
 * enxerga o cadastro completo da organização (`/api/users` é admin-only). */
export function useInviteCandidates(query: string) {
  const q = query.trim();
  return useQuery({
    queryKey: ["finance", "invite-candidates", q],
    queryFn: async () =>
      (
        await api.get<InviteCandidate[]>(
          `/finance/convites-associado/candidatos?q=${encodeURIComponent(q)}`,
        )
      ).data,
    enabled: q.length >= 2,
  });
}

export function useGenerateInvite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (userId: string) =>
      (await api.post<AssociadoInvite>("/finance/convites-associado", { user: userId })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "invites"] }),
  });
}

export function useAcceptAssociadoInvite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (token: string) =>
      (await api.post<BillingProfile>(`/finance/convites-associado/${token}/aceitar`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

export function useSelfSubscribe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (plan: PlanCode) =>
      (await api.post<BillingProfile>("/finance/me/assinar", { plan })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

export function useInitiatePixPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (amount: string) =>
      (await api.post<Payment>("/finance/me/pagar", { amount })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

/** Reconsulta um Pix específico da mensalidade — a tela do QR usa isto pra
 * confirmar sozinha, sem depender só do webhook. Consulta pelo id do
 * pagamento (não "o que está pendente agora"): depois de aprovado, o
 * perfil já não aponta mais pra ele, mas a tela ainda precisa ver o status
 * final antes de fechar o ciclo. */
export function useFinancePixStatus(paymentId: string | null, active: boolean) {
  return useQuery({
    queryKey: ["finance", "pix-status", paymentId],
    enabled: active && !!paymentId,
    refetchInterval: active ? 5_000 : false,
    refetchIntervalInBackground: true,
    queryFn: async () => (await api.get<Payment>(`/finance/me/pagamento/${paymentId}`)).data,
  });
}

export function useDeactivateBilling() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      (await api.post<BillingProfile>(`/billing-profiles/${id}/desativar`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

export function useDues(filters: { billing_profile?: string; user?: string; status?: string }) {
  const { billing_profile, user, status } = filters;
  return useQuery({
    queryKey: ["finance", "dues", { billing_profile, user, status }],
    enabled: !!(billing_profile || user),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (billing_profile) params.set("billing_profile", billing_profile);
      if (user) params.set("user", user);
      if (status) params.set("status", status);
      params.set("page_size", "200");
      return (await api.get<Paginated<Due>>(`/dues?${params.toString()}`)).data.results;
    },
  });
}

export interface RegisterPaymentPayload {
  user: string;
  amount: string;
  method: "dinheiro" | "transferencia" | "pix";
  paid_at: string;
}

export function useRegisterPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: RegisterPaymentPayload) =>
      (await api.post<Due[]>("/dues/registrar-pagamento", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

export function useCancelPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (dueId: string) =>
      (await api.post<Due[]>(`/dues/${dueId}/cancelar-pagamento`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

export interface FinanceDashboard {
  total_users: number;
  up_to_date_count: number;
  paid_in_advance_count: number;
  due_soon_count: number;
  due_today_count: number;
  overdue_count: number;
  delinquent_count: number;
  dues_upcoming_30_days: number;
  dues_overdue: number;
  payments_received: string;
  pending_amount: string;
  advance_payments_received: string;
  upcoming_receivable: string;
}

export function useFinanceDashboard() {
  return useQuery({
    queryKey: ["finance", "dashboard"],
    queryFn: async () => (await api.get<FinanceDashboard>("/finance/dashboard")).data,
  });
}

export interface PlanBreakdown {
  paid_amount: string;
  paid_count: number;
  open_amount: string;
  open_count: number;
}

export interface MonthlyReportRow {
  period: string;
  dues_total_amount: string;
  dues_total_count: number;
  dues_paid_amount: string;
  dues_paid_count: number;
  dues_open_amount: string;
  dues_open_count: number;
  /** Fração 0–1 (em aberto / total do mês) — multiplique por 100 pra exibir. */
  delinquency_rate: string;
  /** Variação % do arrecadado sobre o mês anterior; null sem base de comparação. */
  revenue_change_pct: number | null;
  by_plan: Record<PlanCode, PlanBreakdown>;
}

/** Ano civil (jan–dez) — comparativo mensal completo do painel do admin. */
export function useFinanceMonthlyReport(year: number) {
  return useQuery({
    queryKey: ["finance", "monthly-report", year],
    queryFn: async () =>
      (await api.get<MonthlyReportRow[]>(`/finance/dashboard/mensal?year=${year}`)).data,
  });
}

export interface MyFinanceSummary {
  financial_status: FinancialStatus;
  plan: PlanCode;
  plan_label: string;
  plan_price: string;
  pending_pix_payment_id: string | null;
  due_day: number;
  next_due_date: string | null;
  days_until_due: number | null;
  days_overdue: number;
  months_paid: number;
  months_paid_in_advance: number;
  months_open: number;
  pending_amount: string;
  last_payment_at: string | null;
  paid_through_period: string | null;
}

/** 404 = usuário não está na relação financeira (sem plano ativado ainda). */
export function useMyFinance() {
  return useQuery({
    queryKey: ["finance", "me"],
    queryFn: async () => {
      try {
        return (await api.get<MyFinanceSummary>("/finance/me")).data;
      } catch (err) {
        const status = (err as { response?: { status?: number } }).response?.status;
        if (status === 404) return null;
        throw err;
      }
    },
  });
}

/** Extrato de mensalidades de quem está logado — próprio perfil, sem
 * depender de acesso ao Financeiro (staff-only). Lista vazia = nunca teve plano. */
export function useMyDues() {
  return useQuery({
    queryKey: ["finance", "me", "dues"],
    queryFn: async () => (await api.get<Due[]>("/finance/me/mensalidades")).data,
  });
}
