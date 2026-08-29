import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";

export type FinancialStatus =
  | "up_to_date"
  | "paid_in_advance"
  | "due_soon"
  | "due_today"
  | "overdue"
  | "delinquent";

export const FINANCIAL_STATUS_LABEL: Record<FinancialStatus, string> = {
  up_to_date: "Em dia",
  paid_in_advance: "Pago antecipadamente",
  due_soon: "Próximo do vencimento",
  due_today: "Vencendo hoje",
  overdue: "Vencido",
  delinquent: "Inadimplente",
};

/** Classe de badge (Tabler) por situação — verde a vermelho conforme piora. */
export const FINANCIAL_STATUS_BADGE: Record<FinancialStatus, string> = {
  up_to_date: "bg-green-lt",
  paid_in_advance: "bg-blue-lt",
  due_soon: "bg-yellow-lt",
  due_today: "bg-orange-lt",
  overdue: "bg-red-lt",
  delinquent: "bg-red-lt",
};

export interface BillingProfile {
  id: string;
  user: string;
  user_name: string;
  user_posto: string;
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
  due_day: number;
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

export function useUpdateDueDay() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, due_day }: { id: string; due_day: number }) =>
      (await api.patch<BillingProfile>(`/billing-profiles/${id}`, { due_day })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
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

export interface MyFinanceSummary {
  financial_status: FinancialStatus;
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

/** 404 = usuário não está na relação financeira (Sd/Cb ou nunca ativado). */
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
