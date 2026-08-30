import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";

export interface UserRef {
  id: string;
  username: string;
  email: string;
  nome_guerra: string;
  posto_graduacao: string;
  display_name: string;
  full_name: string;
  cpf: string;
  birth_date: string | null;
  phone: string;
  is_active: boolean;
  roles: string[];
}

interface Paginated<T> {
  results: T[];
  count: number;
}

export const ROLES = [
  { value: "admin", label: "Administrador" },
  { value: "director", label: "Diretor(a) Patrimonial" },
  { value: "inventory", label: "Inventariante" },
  { value: "user", label: "Usuário" },
  { value: "auditor", label: "Auditor" },
  { value: "barbershop", label: "Administrador da Barbearia" },
  { value: "barbershop_client", label: "Cliente da Barbearia" },
];

export const ROLE_LABEL: Record<string, string> = Object.fromEntries(
  ROLES.map((r) => [r.value, r.label]),
);

export interface UserFilters {
  q?: string;
  role?: string;
  /** "true" | "false" — com acesso ou sem acesso. */
  is_active?: string;
  page?: number;
}

/** Página da listagem de usuários (tela de administração). */
export function useUserPage(filters: UserFilters = {}) {
  const { q, role, is_active, page } = filters;
  return useQuery({
    queryKey: [
      "users",
      { q: q ?? null, role: role ?? null, is_active: is_active ?? null, page: page ?? 1 },
    ],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (role) params.set("role", role);
      if (is_active) params.set("is_active", is_active);
      if (page && page > 1) params.set("page", String(page));
      const qs = params.toString();
      return (await api.get<Paginated<UserRef>>(`/users${qs ? `?${qs}` : ""}`)).data;
    },
    placeholderData: (prev) => prev,
  });
}

/** Lista completa para seletores (responsável por cautela, reservar para…). */
export function useUsers(opts: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ["users", { all: true }],
    enabled: opts.enabled ?? true,
    queryFn: async () =>
      (await api.get<Paginated<UserRef>>("/users?page_size=200")).data.results,
  });
}

export interface NewUser {
  /** Obrigatória para quem tem acesso; ignorada quando `is_active` é false. */
  password?: string;
  /** false = pessoa sem acesso ao sistema (só consta em reserva/cautela). */
  is_active?: boolean;
  /** Login. Se vazio, o backend usa o e-mail (ou gera, quando não há acesso). */
  username?: string;
  email?: string;
  full_name?: string;
  nome_guerra?: string;
  posto_graduacao?: string;
  cpf?: string;
  birth_date?: string | null;
  phone?: string;
  role_codes: string[];
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: NewUser) => (await api.post<UserRef>("/users", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
}

export interface UserUpdate {
  username?: string;
  email?: string;
  full_name?: string;
  nome_guerra?: string;
  posto_graduacao?: string;
  cpf?: string;
  birth_date?: string | null;
  phone?: string;
  is_active?: boolean;
  role_codes?: string[];
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: UserUpdate & { id: string }) =>
      (await api.patch<UserRef>(`/users/${id}`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/users/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: async ({ id, new_password }: { id: string; new_password: string }) => {
      await api.post(`/users/${id}/reset-password`, { new_password });
    },
  });
}

// Postos e graduações do Exército Brasileiro (value = abreviatura usada na exibição).
export const MILITARY_RANKS: { group: string; items: { value: string; label: string }[] }[] = [
  {
    group: "Oficiais-Generais",
    items: [
      { value: "Mar", label: "Marechal" },
      { value: "Gen Ex", label: "General de Exército" },
      { value: "Gen Div", label: "General de Divisão" },
      { value: "Gen Bda", label: "General de Brigada" },
    ],
  },
  {
    group: "Oficiais Superiores",
    items: [
      { value: "Cel", label: "Coronel" },
      { value: "Ten Cel", label: "Tenente-Coronel" },
      { value: "Maj", label: "Major" },
    ],
  },
  {
    group: "Oficiais Intermediários",
    items: [{ value: "Cap", label: "Capitão" }],
  },
  {
    group: "Oficiais Subalternos",
    items: [
      { value: "1º Ten", label: "1º Tenente" },
      { value: "2º Ten", label: "2º Tenente" },
      { value: "Asp Of", label: "Aspirante a Oficial" },
    ],
  },
  {
    group: "Praças",
    items: [
      { value: "ST", label: "Subtenente" },
      { value: "1º Sgt", label: "1º Sargento" },
      { value: "2º Sgt", label: "2º Sargento" },
      { value: "3º Sgt", label: "3º Sargento" },
      { value: "Cb", label: "Cabo" },
      { value: "Sd EP", label: "Soldado EP" },
      { value: "Sd EV", label: "Soldado EV" },
    ],
  },
];

// Auto-cadastro público (login por e-mail); a conta já entra ativa.
export interface SignupPayload {
  full_name: string;
  nome_guerra: string;
  posto_graduacao: string;
  cpf: string;
  birth_date: string; // YYYY-MM-DD
  email: string;
  email_confirm: string;
  phone?: string;
  password: string;
}

export function useSignup() {
  return useMutation({
    mutationFn: async (payload: SignupPayload) =>
      (await api.post<UserRef>("/auth/signup", payload)).data,
  });
}

// Edição do próprio perfil. Posto/graduação entra porque muda com promoção;
// o que identifica a pessoa (nome, CPF, nascimento) segue com a administração.
export interface ProfileUpdate {
  email?: string;
  phone?: string;
  nome_guerra?: string;
  posto_graduacao?: string;
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ProfileUpdate) => (await api.patch("/auth/me", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
}

export interface PasswordChange {
  current_password: string;
  new_password: string;
}

export function useChangePassword() {
  return useMutation({
    mutationFn: async (payload: PasswordChange) => {
      await api.post("/auth/me/password", payload);
    },
  });
}
