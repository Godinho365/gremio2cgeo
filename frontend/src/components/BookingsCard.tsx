import { IconCalendarEvent, IconChevronLeft, IconChevronRight } from "@tabler/icons-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { isStaff } from "../auth/roles";
import {
  type Booking,
  useApproveBooking,
  useBookings,
  useCancelBooking,
} from "../features/scheduling/api";
import { addDays } from "../lib/dates";
import IssueCustodyModal from "./IssueCustodyModal";

function fmt(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

/** Reserva aprovada que já começou = bem com a pessoa (cautelado). */
export function isInCourse(b: Booking): boolean {
  const now = Date.now();
  return (
    b.status === "approved" &&
    new Date(b.start_at).getTime() <= now &&
    now < new Date(b.end_at).getTime()
  );
}

function badgeFor(b: Booking): { label: string; cls: string } | null {
  if (b.status === "pending") return { label: "Pendente", cls: "bg-yellow-lt" };
  if (b.status !== "approved") return null;
  return isInCourse(b)
    ? { label: "Cautelado", cls: "bg-red-lt" }
    : { label: "Reservado", cls: "bg-blue-lt" };
}

/**
 * Fila de reservas: pendentes (esperando aprovação) e aprovadas — o bem fica
 * "Reservado" até virar cautela. Sem esta lista só dá para achá-las abrindo a
 * agenda bem a bem.
 */
/** Recorte da lista, comandado pelos cards de situação da página de cautelas. */
export type BookingScope = "all" | "in-course" | "upcoming";

const SCOPE_LABEL: Record<BookingScope, string> = {
  all: "",
  "in-course": "em curso",
  upcoming: "a começar",
};

export default function BookingsCard({
  perPage,
  scope = "all",
}: {
  /** Quando definido, a lista pagina de N em N (usado no dashboard). */
  perPage?: number;
  scope?: BookingScope;
}) {
  const { user } = useAuth();
  const pending = useBookings({ status: "pending" });
  const approved = useBookings({ status: "approved", upcoming: true });
  const approve = useApproveBooking();
  const cancel = useCancelBooking();
  const [custodyFor, setCustodyFor] = useState<Booking | null>(null);
  const [page, setPage] = useState(1);

  const isManager = user?.roles.some((r) => r === "admin" || r === "director") ?? false;
  const isLoading = pending.isLoading || approved.isLoading;
  const all = [...(pending.data?.results ?? []), ...(approved.data?.results ?? [])];
  const inScope =
    scope === "all"
      ? all
      : all.filter((b) => (scope === "in-course" ? isInCourse(b) : b.status === "approved" && !isInCourse(b)));
  // Usuário comum só acompanha as próprias solicitações.
  const mine = isStaff(user) ? inScope : inScope.filter((b) => b.requester === user?.id);
  // "As últimas": as pedidas mais recentemente primeiro.
  const ordenadas = [...mine].sort((a, b) => b.created_at.localeCompare(a.created_at));

  const totalPages = perPage ? Math.max(1, Math.ceil(ordenadas.length / perPage)) : 1;
  const pagina = Math.min(page, totalPages);
  const rows = perPage
    ? ordenadas.slice((pagina - 1) * perPage, pagina * perPage)
    : ordenadas;

  return (
    <>
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">
            <IconCalendarEvent size={18} className="me-2" />
            Reservas
            {scope !== "all" && (
              <span className="text-secondary fw-normal"> · {SCOPE_LABEL[scope]}</span>
            )}
          </h3>
          {perPage && ordenadas.length > 0 && (
            <span className="card-actions text-secondary small">
              {ordenadas.length} {ordenadas.length === 1 ? "reserva" : "reservas"}
            </span>
          )}
        </div>

        {isLoading ? (
          <div className="card-body placeholder-glow">
            <div className="placeholder col-12 mb-2" />
            <div className="placeholder col-9" />
          </div>
        ) : rows.length === 0 ? (
          <div className="card-body text-secondary text-center py-4">
            {scope === "in-course"
              ? "Nenhuma reserva em curso agora."
              : scope === "upcoming"
                ? "Nenhuma reserva marcada para começar."
                : "Nenhuma reserva pendente ou em curso."}
          </div>
        ) : (
          <div className="list-group list-group-flush">
            {rows.map((b) => {
              const badge = badgeFor(b);
              return (
                <div
                  key={b.id}
                  className="list-group-item d-flex align-items-center gap-2 flex-wrap"
                >
                  <div className="flex-fill" style={{ minWidth: 180 }}>
                    <div className="d-flex align-items-center gap-2">
                      <Link
                        to={`/agenda?asset=${b.asset}`}
                        className="text-reset text-decoration-none fw-medium text-truncate"
                        title="Ver na agenda"
                      >
                        {b.asset_name}
                      </Link>
                      {badge && <span className={`badge ${badge.cls}`}>{badge.label}</span>}
                    </div>
                    <div className="text-secondary small">
                      {b.requester_name} · {fmt(b.start_at)} — {fmt(b.end_at)}
                    </div>
                  </div>
                  {isManager ? (
                    <div className="btn-list flex-nowrap">
                      {b.status === "pending" && (
                        <button
                          className="btn btn-sm btn-success"
                          onClick={() => approve.mutate(b.id)}
                          disabled={approve.isPending}
                        >
                          Aprovar
                        </button>
                      )}
                      {b.status === "approved" && (
                        <button className="btn btn-sm btn-primary" onClick={() => setCustodyFor(b)}>
                          Entregar
                        </button>
                      )}
                      <button
                        className="btn btn-sm btn-ghost-danger"
                        onClick={() => {
                          if (confirm("Cancelar esta reserva?")) cancel.mutate(b.id);
                        }}
                        disabled={cancel.isPending}
                      >
                        Cancelar
                      </button>
                    </div>
                  ) : (
                    <Link
                      to={`/agenda?asset=${b.asset}`}
                      className="btn btn-sm btn-ghost-secondary"
                      title="Ver na agenda"
                    >
                      <IconChevronRight size={16} />
                    </Link>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {perPage && totalPages > 1 && (
          <div className="card-footer d-flex align-items-center gap-2">
            <span className="text-secondary small">
              Página {pagina} de {totalPages}
            </span>
            <div className="ms-auto d-flex gap-2">
              <button
                className="btn btn-sm btn-outline-secondary"
                disabled={pagina <= 1}
                onClick={() => setPage(pagina - 1)}
                title="Reservas mais recentes"
              >
                <IconChevronLeft size={16} />
              </button>
              <button
                className="btn btn-sm btn-outline-secondary"
                disabled={pagina >= totalPages}
                onClick={() => setPage(pagina + 1)}
                title="Reservas anteriores"
              >
                <IconChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>

      {custodyFor && (
        <IssueCustodyModal
          asset={custodyFor.asset}
          assetLabel={custodyFor.asset_name}
          defaultHolder={custodyFor.requester}
          defaultIssued={custodyFor.start_at.slice(0, 10)}
          // end_at é exclusivo (dia seguinte 00:00) → último dia da reserva = -1 dia
          defaultDue={addDays(custodyFor.end_at.slice(0, 10), -1)}
          bookingId={custodyFor.id}
          onClose={() => setCustodyFor(null)}
        />
      )}
    </>
  );
}
