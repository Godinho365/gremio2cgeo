import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";

export interface Asset {
  id: string;
  asset_tag: string;
  name: string;
  status: string;
  condition: string;
  category_name: string | null;
  location_name: string | null;
  created_at: string;
}

interface Paginated<T> {
  results: T[];
  count: number;
}

export function useAssets() {
  return useQuery({
    queryKey: ["assets"],
    queryFn: async () => (await api.get<Paginated<Asset>>("/assets")).data,
  });
}

export interface NewAsset {
  name: string;
  description?: string;
  condition?: string;
  category?: string | null;
  location?: string | null;
}

export function useCreateAsset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: NewAsset) => (await api.post<Asset>("/assets", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["assets"] }),
  });
}

export interface NamedRef {
  id: string;
  name: string;
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

export const CONDITIONS = [
  { value: "new", label: "Novo" },
  { value: "good", label: "Bom" },
  { value: "regular", label: "Regular" },
  { value: "bad", label: "Ruim" },
  { value: "unusable", label: "Inservível" },
];
