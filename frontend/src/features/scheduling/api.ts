import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";

export interface Booking {
  id: string;
  asset: string;
  asset_tag: string;
  asset_name: string;
  requester: string;
  requester_name: string;
  start_at: string;
  end_at: string;
  status: "pending" | "approved" | "rejected" | "cancelled" | "completed";
  notes: string;
  created_at: string;
}

interface Paginated<T> {
  results: T[];
  count: number;
}

export const BOOKING_STATUS: Record<Booking["status"], { label: string; cls: string }> = {
  pending: { label: "Pendente", cls: "bg-yellow-lt" },
  approved: { label: "Aprovada", cls: "bg-green-lt" },
  rejected: { label: "Recusada", cls: "bg-red-lt" },
  cancelled: { label: "Cancelada", cls: "bg-secondary-lt" },
  completed: { label: "Concluída", cls: "bg-blue-lt" },
};

export interface BookingFilters {
  asset?: string;
  status?: Booking["status"];
  /** Só as que ainda não terminaram. */
  upcoming?: boolean;
}

export function useBookings(filters: BookingFilters = {}) {
  const { asset, status, upcoming } = filters;
  return useQuery({
    queryKey: [
      "bookings",
      { asset: asset ?? null, status: status ?? null, upcoming: !!upcoming },
    ],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (asset) params.set("asset", asset);
      if (status) params.set("status", status);
      if (upcoming) params.set("upcoming", "1");
      const qs = params.toString();
      return (await api.get<Paginated<Booking>>(`/bookings${qs ? `?${qs}` : ""}`)).data;
    },
  });
}

export interface Availability {
  id: string;
  asset: string;
  weekday: number; // 0=Segunda … 6=Domingo (backend)
  start_time: string; // "HH:MM:SS"
  end_time: string;
  slot_minutes: number;
}

export function useAvailabilities(asset?: string) {
  return useQuery({
    queryKey: ["availabilities", asset ?? "all"],
    enabled: !!asset,
    queryFn: async () => {
      const q = asset ? `?asset=${asset}` : "";
      return (await api.get<Paginated<Availability>>(`/availabilities${q}`)).data.results;
    },
  });
}

export interface NewAvailability {
  asset: string;
  weekday: number;
  start_time: string;
  end_time: string;
}

export function useCreateAvailability() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: NewAvailability) =>
      (await api.post<Availability>("/availabilities", payload)).data,
    onSuccess: (_d, v) =>
      qc.invalidateQueries({ queryKey: ["availabilities", v.asset] }),
  });
}

export interface NewBooking {
  asset: string;
  start_at: string;
  end_at: string;
  notes?: string;
  /** Reserva em nome de outro usuário — só Admin/Diretor. */
  requester?: string;
}

export function useCreateBooking() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: NewBooking) =>
      (await api.post<Booking>("/bookings", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bookings"] }),
  });
}

function useBookingAction(action: "approve" | "cancel") {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => (await api.post<Booking>(`/bookings/${id}/${action}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bookings"] }),
  });
}

export const useApproveBooking = () => useBookingAction("approve");
export const useCancelBooking = () => useBookingAction("cancel");

export function useDeleteBooking() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/bookings/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bookings"] }),
  });
}
