import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";

export interface UserRef {
  id: string;
  username: string;
  email: string;
  nome_guerra: string;
  posto_graduacao: string;
  display_name: string;
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
];

export const ROLE_LABEL: Record<string, string> = Object.fromEntries(
  ROLES.map((r) => [r.value, r.label]),
);

export function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: async () => (await api.get<Paginated<UserRef>>("/users")).data.results,
  });
}

export interface NewUser {
  username: string;
  password: string;
  email?: string;
  nome_guerra?: string;
  posto_graduacao?: string;
  role_codes: string[];
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: NewUser) => (await api.post<UserRef>("/users", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
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
      { value: "Sd", label: "Soldado" },
    ],
  },
];

// Auto-cadastro público de usuário (login por e-mail).
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
