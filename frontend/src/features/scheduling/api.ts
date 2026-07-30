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

export function useBookings(asset?: string) {
  return useQuery({
    queryKey: ["bookings", asset ?? "all"],
    queryFn: async () => {
      const q = asset ? `?asset=${asset}` : "";
      return (await api.get<Paginated<Booking>>(`/bookings${q}`)).data;
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
