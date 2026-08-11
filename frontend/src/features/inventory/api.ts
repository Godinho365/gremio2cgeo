import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";

export interface Inventory {
  id: string;
  title: string;
  status: "open" | "closed";
  /** 1º dia do mês conferido (a conferência é mensal). */
  reference_month: string | null;
  responsible_name: string;
  created_at: string;
  closed_at: string | null;
}

export interface InventoryItem {
  id: string;
  asset: string;
  asset_tag: string;
  asset_name: string;
  expected_location_name: string | null;
  found: boolean;
  found_location: string | null;
  found_location_name: string | null;
  condition_found: string;
  discrepancy: "none" | "not_found" | "wrong_location";
  /** Com quem o bem está hoje — no dia da conferência, vale como local. */
  holder_name: string | null;
  scanned_at: string | null;
}

export interface InventoryReport {
  total: number;
  found: number;
  not_found: number;
  wrong_location: number;
}

interface Paginated<T> {
  results: T[];
  count: number;
}

export const DISCREPANCY_META: Record<string, { label: string; cls: string }> = {
  none: { label: "OK", cls: "bg-green-lt" },
  not_found: { label: "Não encontrado", cls: "bg-secondary-lt" },
  wrong_location: { label: "Local divergente", cls: "bg-orange-lt" },
};

export function useInventories() {
  return useQuery({
    queryKey: ["inventories"],
    queryFn: async () => (await api.get<Paginated<Inventory>>("/inventories")).data,
  });
}

export function useOpenInventory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (title: string) =>
      (await api.post<Inventory>("/inventories", { title })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inventories"] }),
  });
}

export function useRenameInventory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, title }: { id: string; title: string }) =>
      (await api.patch<Inventory>(`/inventories/${id}`, { title })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inventories"] }),
  });
}

export function useDeleteInventory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/inventories/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inventories"] }),
  });
}

export function useInventoryItems(id: string) {
  return useQuery({
    queryKey: ["inventory-items", id],
    queryFn: async () => (await api.get<InventoryItem[]>(`/inventories/${id}/items`)).data,
  });
}

export function useInventoryReport(id: string) {
  return useQuery({
    queryKey: ["inventory-report", id],
    queryFn: async () => (await api.get<InventoryReport>(`/inventories/${id}/report`)).data,
  });
}

export function useScanItem(inventoryId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { item: string; found_location?: string | null; condition_found?: string }) =>
      (await api.post(`/inventories/${inventoryId}/scan`, body)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["inventory-items", inventoryId] });
      qc.invalidateQueries({ queryKey: ["inventory-report", inventoryId] });
    },
  });
}

export function useCloseInventory(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => (await api.post(`/inventories/${id}/close`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["inventories"] });
    },
  });
}
