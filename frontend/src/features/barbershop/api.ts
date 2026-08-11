import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";

export interface BarberSchedule {
  id: string;
  weekday: number;
  weekday_label: string;
  start_time: string; // "09:00:00"
  end_time: string;
  slot_minutes: number;
}

export interface BarberTimeOff {
  id: string;
  start_date: string; // "2026-08-20"
  end_date: string; // igual ao início quando é um dia só
  /** Quantos dias o período cobre. */
  days: number;
  reason: string;
}

export interface Barber {
  id: string;
  name: string;
  nickname: string;
  display_name: string;
  phone: string;
  photo_data: string;
  is_active: boolean;
  schedules: BarberSchedule[];
  time_off: BarberTimeOff[];
  created_at: string;
}

export interface Slot {
  start_at: string;
  end_at: string;
}

export interface Payment {
  id: string;
  method: "pix";
  amount: string;
  status: "pending" | "approved" | "rejected" | "cancelled" | "expired" | "refunded";
  status_label: string;
  /** Pix copia-e-cola. */
  qr_code: string;
  /** PNG do QR em base64 (sem o prefixo data:). */
  qr_code_base64: string;
  ticket_url: string;
  expires_at: string | null;
  paid_at: string | null;
}

export interface Appointment {
  id: string;
  barber: string;
  barber_name: string;
  customer: string;
  customer_name: string;
  start_at: string;
  end_at: string;
  is_subscriber: boolean;
  price: string;
  /** Cobrança Pix do avulso; assinante não tem. */
  payment: Payment | null;
  /** Pago com crédito do perfil — não passou pelo Pix. */
  paid_with_credit: boolean;
  /** Situação pelo relógio: agendado → ativo → finalizado (o backend calcula). */
  status:
    | "awaiting_payment"
    | "scheduled"
    | "active"
    | "completed"
    | "cancelled"
    | "no_show";
  status_label: string;
  /** Ainda dá para remarcar/cancelar (até 10 min antes). */
  can_change: boolean;
  /** Instante em que a janela de alteração se fecha. */
  change_deadline: string;
  notes: string;
  created_at: string;
}

export interface CreditEntry {
  id: string;
  /** Positivo credita, negativo debita. Ex.: "15.00" ou "-15.00". */
  amount: string;
  reason: "appointment_cancelled" | "used_in_appointment" | "manual";
  reason_label: string;
  note: string;
  created_at: string;
}

export interface CreditBalance {
  balance: string;
  entries: CreditEntry[];
}

/** Saldo e extrato de crédito de quem está logado. */
export function useCredits() {
  return useQuery({
    queryKey: ["credits"],
    queryFn: async () => (await api.get<CreditBalance>("/credits")).data,
  });
}

export interface Quota {
  limit: number;
  used: number;
  remaining: number;
}

interface Paginated<T> {
  results: T[];
  count: number;
}

export const WEEKDAYS = [
  { value: 0, label: "Segunda", short: "Seg" },
  { value: 1, label: "Terça", short: "Ter" },
  { value: 2, label: "Quarta", short: "Qua" },
  { value: 3, label: "Quinta", short: "Qui" },
  { value: 4, label: "Sexta", short: "Sex" },
  { value: 5, label: "Sábado", short: "Sáb" },
  { value: 6, label: "Domingo", short: "Dom" },
];

export const APPOINTMENT_STATUS_META: Record<string, { label: string; cls: string }> = {
  awaiting_payment: { label: "Aguardando pagamento", cls: "bg-yellow-lt" },
  scheduled: { label: "Agendado", cls: "bg-blue-lt" },
  active: { label: "Ativo", cls: "bg-azure-lt" },
  completed: { label: "Finalizado", cls: "bg-green-lt" },
  cancelled: { label: "Cancelado", cls: "bg-secondary-lt" },
  no_show: { label: "Não compareceu", cls: "bg-orange-lt" },
};


/** "15.00" (decimal da API) → "15,00". */
export const brl = (valor: string | number) =>
  Number(valor).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Minutos antes da hora em que remarcar e cancelar deixam de valer. */
export const CHANGE_CUTOFF_MINUTES = 10;

// ── Barbeiros ────────────────────────────────────────────────────────────────

/** `date` limita aos barbeiros que atendem naquele dia (passo 2 do agendamento). */
export function useBarbers(opts: { date?: string; onlyActive?: boolean } = {}) {
  const { date, onlyActive } = opts;
  return useQuery({
    queryKey: ["barbers", { date: date ?? null, onlyActive: !!onlyActive }],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (date) params.set("date", date);
      if (onlyActive) params.set("active", "1");
      params.set("page_size", "100");
      return (await api.get<Paginated<Barber>>(`/barbers?${params}`)).data.results;
    },
  });
}

export interface BarberInput {
  name?: string;
  nickname?: string;
  phone?: string;
  photo_data?: string;
  is_active?: boolean;
}

export function useCreateBarber() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: BarberInput) => (await api.post<Barber>("/barbers", body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["barbers"] }),
  });
}

export function useUpdateBarber() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: BarberInput & { id: string }) =>
      (await api.patch<Barber>(`/barbers/${id}`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["barbers"] }),
  });
}

export function useDeleteBarber() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/barbers/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["barbers"] }),
  });
}

export interface ScheduleWindow {
  weekday: number;
  start_time: string;
  end_time: string;
  slot_minutes: number;
}

/** Aplica a grade de um barbeiro nos outros escolhidos. */
export function useReplicateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, targets }: { id: string; targets: string[] }) =>
      (await api.post<{ updated: number }>(`/barbers/${id}/horarios/replicar`, { targets })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["barbers"] });
      qc.invalidateQueries({ queryKey: ["slots"] });
    },
  });
}

export function useSetSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, windows }: { id: string; windows: ScheduleWindow[] }) =>
      (await api.put<Barber>(`/barbers/${id}/horarios`, { windows })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["barbers"] });
      qc.invalidateQueries({ queryKey: ["slots"] });
    },
  });
}

export interface TimeOffInput {
  id: string;
  start_date: string;
  /** Ausente ou igual ao início = folga de um dia só. */
  end_date?: string;
  reason: string;
}

export function useAddTimeOff() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: TimeOffInput) =>
      (await api.post<BarberTimeOff>(`/barbers/${id}/folgas`, body)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["barbers"] });
      qc.invalidateQueries({ queryKey: ["slots"] });
    },
  });
}

export function useRemoveTimeOff() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, offId }: { id: string; offId: string }) => {
      await api.delete(`/barbers/${id}/folgas/${offId}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["barbers"] });
      qc.invalidateQueries({ queryKey: ["slots"] });
    },
  });
}

/** Horários livres do barbeiro no dia. Só consulta quando os dois estão escolhidos. */
export function useSlots(barberId: string | null, date: string | null) {
  return useQuery({
    queryKey: ["slots", barberId, date],
    enabled: !!barberId && !!date,
    queryFn: async () =>
      (await api.get<Slot[]>(`/barbers/${barberId}/horarios-livres?date=${date}`)).data,
  });
}

// ── Agendamentos ─────────────────────────────────────────────────────────────

export interface AppointmentFilters {
  /** "mine" (padrão) ou "all" — "all" só vale para a administração. */
  scope?: "mine" | "all";
  date?: string;
  barber?: string;
  status?: string;
  upcoming?: boolean;
  page?: number;
  pageSize?: number;
}

export function useAppointments(filters: AppointmentFilters = {}) {
  const { scope, date, barber, status, upcoming, page, pageSize } = filters;
  return useQuery({
    queryKey: ["appointments", filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (scope) params.set("scope", scope);
      if (date) params.set("date", date);
      if (barber) params.set("barber", barber);
      if (status) params.set("status", status);
      if (upcoming) params.set("upcoming", "1");
      if (page && page > 1) params.set("page", String(page));
      if (pageSize) params.set("page_size", String(pageSize));
      return (await api.get<Paginated<Appointment>>(`/appointments?${params}`)).data;
    },
    // A situação vem do relógio do servidor: reconsultar de minuto em minuto é
    // o que faz "Agendado" virar "Ativo" e depois "Finalizado" sozinho na tela.
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
    placeholderData: (prev) => prev,
  });
}

/**
 * Consulta o Pix no provedor e devolve o agendamento já atualizado. Roda em
 * laço enquanto o QR está na tela: o webhook pode não chegar (instalação em
 * rede interna), então quem garante a confirmação é esta consulta.
 */
export function usePaymentStatus(appointmentId: string | null, active: boolean) {
  return useQuery({
    queryKey: ["appointment-payment", appointmentId],
    enabled: !!appointmentId && active,
    refetchInterval: active ? 5_000 : false,
    // Pagar Pix é sair para o app do banco, ou pagar de outro aparelho: sem
    // isto o React Query pausa o laço com a aba fora de foco e a confirmação
    // só chegaria quando a pessoa voltasse para a tela.
    refetchIntervalInBackground: true,
    queryFn: async () =>
      (await api.get<Appointment>(`/appointments/${appointmentId}/pagamento`)).data,
  });
}

export interface PaymentConfig {
  /** Sem isso o corte avulso não pode ser marcado. */
  pix_enabled: boolean;
  /** Preço do avulso, como o servidor cobra. Ex.: "15.00". */
  walk_in_price: string;
  pix_expiry_minutes: number;
}

/** Configuração de cobrança. O preço vem do servidor — nunca fixo na tela. */
export function usePaymentConfig() {
  return useQuery({
    queryKey: ["payment-config"],
    staleTime: 5 * 60_000,
    queryFn: async () => (await api.get<PaymentConfig>("/payments/config")).data,
  });
}

export function useQuota(date: string) {
  return useQuery({
    queryKey: ["barber-quota", date],
    queryFn: async () => (await api.get<Quota>(`/appointments/cota?date=${date}`)).data,
  });
}

function invalidateBooking(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["appointments"] });
  qc.invalidateQueries({ queryKey: ["slots"] });
  qc.invalidateQueries({ queryKey: ["barber-quota"] });
  // Marcar e cancelar mexem no crédito; o saldo na tela não pode ficar velho.
  qc.invalidateQueries({ queryKey: ["credits"] });
}

export interface BookInput {
  barber: string;
  start_at: string;
  is_subscriber: boolean;
  notes?: string;
  customer?: string;
}

export function useBook() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: BookInput) =>
      (await api.post<Appointment>("/appointments", body)).data,
    onSuccess: () => invalidateBooking(qc),
  });
}

export function useReschedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, start_at, barber }: { id: string; start_at: string; barber?: string }) =>
      (await api.post<Appointment>(`/appointments/${id}/remarcar`, { start_at, barber })).data,
    onSuccess: () => invalidateBooking(qc),
  });
}

export function useCancelAppointment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      (await api.post<Appointment>(`/appointments/${id}/cancelar`)).data,
    onSuccess: () => invalidateBooking(qc),
  });
}

export function useFinishAppointment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, noShow }: { id: string; noShow?: boolean }) =>
      (await api.post<Appointment>(`/appointments/${id}/concluir`, { no_show: !!noShow })).data,
    onSuccess: () => invalidateBooking(qc),
  });
}
