import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";

export interface Asset {
  id: string;
  asset_tag: string;
  name: string;
  description: string;
  status: string;
  condition: string;
  category: string | null;
  location: string | null;
  category_name: string | null;
  location_name: string | null;
  protection_notes: string;
  is_bookable: boolean;
  plan_x: number | null;
  plan_y: number | null;
  created_at: string;
}

interface Paginated<T> {
  results: T[];
  count: number;
}

export const CONDITIONS = [
  { value: "new", label: "Novo" },
  { value: "good", label: "Bom" },
  { value: "regular", label: "Regular" },
  { value: "bad", label: "Ruim" },
  { value: "unusable", label: "Inservível" },
];

export const ASSET_STATUS = [
  { value: "available", label: "Disponível", cls: "bg-green-lt" },
  { value: "reserved", label: "Reservado", cls: "bg-yellow-lt" },
  { value: "in_use", label: "Em uso", cls: "bg-blue-lt" },
  { value: "maintenance", label: "Manutenção", cls: "bg-orange-lt" },
  { value: "written_off", label: "Baixado", cls: "bg-secondary-lt" },
];

export const STATUS_META: Record<string, { label: string; cls: string }> = Object.fromEntries(
  ASSET_STATUS.map((s) => [s.value, { label: s.label, cls: s.cls }]),
);

export const LOCATION_TYPES = [
  { value: "unit", label: "Unidade" },
  { value: "building", label: "Prédio" },
  { value: "floor", label: "Andar" },
  { value: "room", label: "Sala" },
];

export function useAssets() {
  return useQuery({
    queryKey: ["assets"],
    queryFn: async () => (await api.get<Paginated<Asset>>("/assets")).data,
  });
}

export interface AssetInput {
  name?: string;
  description?: string;
  condition?: string;
  status?: string;
  category?: string | null;
  location?: string | null;
  is_bookable?: boolean;
  protection_notes?: string;
  plan_x?: number | null;
  plan_y?: number | null;
}

export function useCreateAsset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: AssetInput) => (await api.post<Asset>("/assets", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["assets"] }),
  });
}

export function useUpdateAsset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: AssetInput & { id: string }) =>
      (await api.patch<Asset>(`/assets/${id}`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["assets"] }),
  });
}

export interface NamedRef {
  id: string;
  name: string;
  type?: string;
}

export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: async () => (await api.get<Paginated<NamedRef>>("/categories")).data.results,
  });
}

export function useLocations() {
  return useQuery({
    queryKey: ["locations"],
    queryFn: async () => (await api.get<Paginated<NamedRef>>("/locations")).data.results,
  });
}

export function useCreateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) => (await api.post("/categories", { name })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["categories"] }),
  });
}

export function useDeleteCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/categories/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["categories"] }),
  });
}

export function useCreateLocation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name: string; type: string }) =>
      (await api.post("/locations", body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["locations"] }),
  });
}

export function useDeleteLocation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/locations/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["locations"] }),
  });
}

/** Fetches the QR PNG (auth-protected) as a base64 data URL (usable for print). */
export async function fetchAssetQrUrl(id: string): Promise<string> {
  const resp = await api.get(`/assets/${id}/qrcode`, { responseType: "blob" });
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(resp.data as Blob);
  });
}

// ── Planta da sala (floor plan) ──────────────────────────────────────────────
export interface FloorPlan {
  id: string;
  name: string;
  image_data: string; // data URI (base64)
  updated_at: string;
}

export function useFloorPlan() {
  return useQuery({
    queryKey: ["floorplan"],
    queryFn: async () =>
      (await api.get<Paginated<FloorPlan>>("/floorplans")).data.results[0] ?? null,
  });
}

export function useSaveFloorPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { id?: string; name?: string; image_data: string }) => {
      if (payload.id) {
        return (await api.patch<FloorPlan>(`/floorplans/${payload.id}`, payload)).data;
      }
      return (
        await api.post<FloorPlan>("/floorplans", {
          name: payload.name ?? "Planta",
          image_data: payload.image_data,
        })
      ).data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["floorplan"] }),
  });
}
