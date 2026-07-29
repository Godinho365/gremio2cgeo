import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";

export interface Booking {
  id: string;
  asset: string;
  asset_tag: string;
  asset_name: string;
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

export function useBookings() {
  return useQuery({
    queryKey: ["bookings"],
    queryFn: async () => (await api.get<Paginated<Booking>>("/bookings")).data,
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
