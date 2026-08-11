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
  photo_data: string; // data URI (base64) ou ""
  has_open_custody: boolean; // cautela ativa ou atrasada
  is_reserved_now: boolean; // reserva aprovada cobrindo agora (bem já saiu)
  has_upcoming_booking: boolean; // reserva aprovada que ainda vai começar
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

export interface AssetFilters {
  q?: string;
  category?: string;
  location?: string;
  status?: string;
  page?: number;
  /** Só bens reserváveis (catálogo). */
  bookable?: boolean;
  /** Lista inteira num seletor (o backend limita a 200). */
  pageSize?: number;
}

export function useAssets(filters: AssetFilters = {}) {
  const { q, category, location, status, page, bookable, pageSize } = filters;
  return useQuery({
    queryKey: [
      "assets",
      {
        q: q ?? null,
        category: category ?? null,
        location: location ?? null,
        status: status ?? null,
        page: page ?? 1,
        bookable: !!bookable,
        pageSize: pageSize ?? null,
      },
    ],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (category) params.set("category", category);
      if (location) params.set("location", location);
      if (status) params.set("status", status);
      if (page && page > 1) params.set("page", String(page));
      if (bookable) params.set("bookable", "1");
      if (pageSize) params.set("page_size", String(pageSize));
      const qs = params.toString();
      return (await api.get<Paginated<Asset>>(`/assets${qs ? `?${qs}` : ""}`)).data;
    },
    placeholderData: (prev) => prev, // evita "piscar" ao digitar na busca
  });
}

export interface AssetStats {
  available: number;
  reserved: number;
  in_use: number;
  maintenance: number;
  written_off: number;
  total: number;
}

export function useAssetStats(opts: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ["asset-stats"],
    enabled: opts.enabled ?? true,
    queryFn: async () => (await api.get<AssetStats>("/assets/stats")).data,
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
  photo_data?: string;
}

export function useCreateAsset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: AssetInput) => (await api.post<Asset>("/assets", payload)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assets"] });
      qc.invalidateQueries({ queryKey: ["asset-stats"] });
    },
  });
}

export function useUpdateAsset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: AssetInput & { id: string }) =>
      (await api.patch<Asset>(`/assets/${id}`, body)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assets"] });
      qc.invalidateQueries({ queryKey: ["asset-stats"] });
    },
  });
}

export function useDeleteAsset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/assets/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assets"] });
      qc.invalidateQueries({ queryKey: ["asset-stats"] });
    },
  });
}

export interface NamedRef {
  id: string;
  name: string;
  type?: string;
  /** Quantos bens usam este registro (bloqueia a exclusão quando > 0). */
  asset_count: number;
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

export function useRenameCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, name }: { id: string; name: string }) =>
      (await api.patch(`/categories/${id}`, { name })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["categories"] });
      qc.invalidateQueries({ queryKey: ["assets"] });
    },
  });
}

export function useRenameLocation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, name }: { id: string; name: string }) =>
      (await api.patch(`/locations/${id}`, { name })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["locations"] });
      qc.invalidateQueries({ queryKey: ["assets"] });
    },
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
    // `type` continua no modelo com o padrão "sala"; a tela não pergunta mais.
    mutationFn: async (name: string) => (await api.post("/locations", { name })).data,
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
