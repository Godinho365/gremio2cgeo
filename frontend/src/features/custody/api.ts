import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";

export interface Custody {
  id: string;
  asset: string;
  asset_tag: string;
  asset_name: string;
  holder: string;
  holder_name: string;
  issued_by_name: string;
  issued_at: string;
  due_at: string;
  condition_out: string;
  status: "pending" | "active" | "rejected" | "returned" | "overdue" | "lost";
  term_hash: string;
  notes: string;
}

interface Paginated<T> {
  results: T[];
  count: number;
}

export const CUSTODY_STATUS: Record<Custody["status"], { label: string; cls: string }> = {
  pending: { label: "Solicitada", cls: "bg-yellow-lt" },
  active: { label: "Ativa", cls: "bg-green-lt" },
  rejected: { label: "Rejeitada", cls: "bg-secondary-lt" },
  returned: { label: "Devolvida", cls: "bg-secondary-lt" },
  overdue: { label: "Atrasada", cls: "bg-red-lt" },
  lost: { label: "Extraviada", cls: "bg-red-lt" },
};

export function useCustodies(asset?: string) {
  return useQuery({
    queryKey: ["custodies", asset ?? "all"],
    queryFn: async () => {
      const q = asset ? `?asset=${asset}` : "";
      return (await api.get<Paginated<Custody>>(`/custodies${q}`)).data;
    },
  });
}

export interface IssueCustody {
  asset: string;
  holder: string;
  booking?: string | null;
  due_at: string;
  condition_out: string;
  notes?: string;
}

export function useIssueCustody() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: IssueCustody) =>
      (await api.post<Custody>("/custodies", payload)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["custodies"] });
      qc.invalidateQueries({ queryKey: ["assets"] });
      qc.invalidateQueries({ queryKey: ["bookings"] });
    },
  });
}

function useCustodyAction(action: "approve" | "reject") {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      (await api.post<Custody>(`/custodies/${id}/${action}`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["custodies"] });
      qc.invalidateQueries({ queryKey: ["assets"] });
    },
  });
}

export const useApproveCustody = () => useCustodyAction("approve");
export const useRejectCustody = () => useCustodyAction("reject");

export function useDeleteCustody() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/custodies/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["custodies"] }),
  });
}

export interface ReturnCustody {
  condition_in: string;
  outcome: "ok" | "damage" | "missing";
  notes?: string;
}

export function useReturnCustody() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: ReturnCustody & { id: string }) =>
      (await api.post<Custody>(`/custodies/${id}/return`, body)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["custodies"] });
      qc.invalidateQueries({ queryKey: ["assets"] });
    },
  });
}

export const OUTCOMES = [
  { value: "ok", label: "Sem dano — bem íntegro" },
  { value: "damage", label: "Com dano — enviar p/ manutenção" },
  { value: "missing", label: "Faltante — registrar extravio" },
];
