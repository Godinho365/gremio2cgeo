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
