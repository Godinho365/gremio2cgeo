import ptBrLocale from "@fullcalendar/core/locales/pt-br";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import {
  IconAlertTriangle,
  IconCalendarEvent,
  IconChevronRight,
  IconClipboardCheck,
  IconClock,
  IconPackage,
} from "@tabler/icons-react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import AssetPicker, { type AssetStateInfo } from "../components/AssetPicker";
import IssueCustodyModal from "../components/IssueCustodyModal";
import { useAssets } from "../features/assets/api";
import { useCustodies } from "../features/custody/api";
import {
  type Booking,
  useApproveBooking,
  useBookings,
  useCancelBooking,
  useCreateBooking,
} from "../features/scheduling/api";

// Paleta profissional (sem verde de "disponível" — o backend não usa agenda de dias).
const PENDING = "#f59f00"; // aguardando aprovação
const APPROVED = "#206bc4"; // reserva confirmada
const CUSTODY = "#d63939"; // bem em uso (cautelado)

type EventKind = "pending" | "approved" | "custody" | "custody_pending";

const KIND_META: Record<EventKind, { label: string; color: string }> = {
  pending: { label: "Reserva pendente", color: PENDING },
  approved: { label: "Aprovada", color: APPROVED },
  custody: { label: "Cautelado", color: CUSTODY },
  custody_pending: { label: "Cautela solicitada", color: PENDING },
};

const pad = (n: number) => String(n).padStart(2, "0");
const dateStr = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return dateStr(d);
}
function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}
function relativeDay(iso: string): string {
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const target = startOfDay(new Date(iso));
  const today = startOfDay(new Date());
  const diff = Math.round((target.getTime() - today.getTime()) / 86_400_000);
  if (diff === 0) return "Hoje";
  if (diff === 1) return "Amanhã";
  if (diff === -1) return "Ontem";
  if (diff > 1) return `em ${diff} dias`;
  return `há ${-diff} dias`;
}

// ── Modais ──────────────────────────────────────────────────────────────────
function BookingModal({
  asset,
  initialStart,
  initialEnd,
  onClose,
}: {
  asset: string;
  initialStart: string;
  initialEnd: string;
  onClose: () => void;
}) {
  const create = useCreateBooking();
  const today = dateStr(new Date());
  const [start, setStart] = useState(initialStart);
  const [end, setEnd] = useState(initialEnd);
  const [error, setError] = useState<string | null>(null);

  const startPast = start !== "" && start < today; // início no passado
  const endBeforeStart = end !== "" && start !== "" && end < start; // término antes do início
  const invalid = !start || !end || startPast || endBeforeStart;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (startPast) {
      setError("Não é possível reservar em datas passadas.");
      return;
    }
    if (endBeforeStart) {
      setError("A data final não pode ser anterior à inicial.");
      return;
    }
    try {
      // datas inclusivas -> intervalo meio-aberto [start 00:00, (end+1) 00:00)
      await create.mutateAsync({
        asset,
        start_at: `${start}T00:00:00`,
        end_at: `${addDays(end, 1)}T00:00:00`,
      });
      onClose();
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response
        ?.data?.error?.message;
      setError(msg ?? "Não foi possível criar a reserva.");
    }
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Nova reserva</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                {error && <div className="alert alert-danger">{error}</div>}
                <div className="row">
                  <div className="col-6 mb-3">
                    <label className="form-label required">De</label>
                    <input
                      type="date"
                      className={`form-control${startPast ? " is-invalid" : ""}`}
                      value={start}
                      min={today}
                      onChange={(e) => setStart(e.target.value)}
                      required
                    />
                    {startPast && (
                      <div className="invalid-feedback d-block">
                        Não é possível reservar em datas passadas.
                      </div>
                    )}
                  </div>
                  <div className="col-6 mb-3">
                    <label className="form-label required">Até</label>
                    <input
                      type="date"
                      className={`form-control${endBeforeStart ? " is-invalid" : ""}`}
                      value={end}
                      min={start || today}
                      onChange={(e) => setEnd(e.target.value)}
                      required
                    />
                    {endBeforeStart && (
                      <div className="invalid-feedback d-block">
                        A data final não pode ser anterior à inicial.
                      </div>
                    )}
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={create.isPending || invalid}
                >
                  {create.isPending ? "Salvando…" : "Reservar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
      <div className="modal-backdrop fade show" />
    </>
  );
}

function BookingDetailModal({
  booking,
  isManager,
  onEmitCustody,
  onClose,
}: {
  booking: Booking;
  isManager: boolean;
  onEmitCustody: (b: Booking) => void;
  onClose: () => void;
}) {
  const approve = useApproveBooking();
  const cancel = useCancelBooking();
  const active = booking.status === "pending" || booking.status === "approved";
  const meta = booking.status === "approved" ? KIND_META.approved : KIND_META.pending;

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-status" style={{ backgroundColor: meta.color }} />
            <div className="modal-header">
              <h5 className="modal-title">Reserva — {booking.asset_name}</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <div className="modal-body">
              <dl className="row mb-0">
                <dt className="col-4">Solicitante</dt>
                <dd className="col-8">{booking.requester_name}</dd>
                <dt className="col-4">Período</dt>
                <dd className="col-8">
                  {fmtDate(booking.start_at)} — {fmtDate(booking.end_at)}
                </dd>
                <dt className="col-4">Situação</dt>
                <dd className="col-8">
                  <span
                    className="badge"
                    style={{ backgroundColor: meta.color, color: "#fff" }}
                  >
                    {meta.label}
                  </span>
                </dd>
              </dl>
            </div>
            <div className="modal-footer">
              {isManager && booking.status === "pending" && (
                <button
                  className="btn btn-success"
                  onClick={() => approve.mutate(booking.id, { onSuccess: onClose })}
                  disabled={approve.isPending}
                >
                  Aprovar
                </button>
              )}
              {isManager && booking.status === "approved" && (
                <button className="btn btn-primary" onClick={() => onEmitCustody(booking)}>
                  Solicitar cautela
                </button>
              )}
              {active && (
                <button
                  className="btn btn-ghost-danger"
                  onClick={() => cancel.mutate(booking.id, { onSuccess: onClose })}
                  disabled={cancel.isPending}
                >
                  Cancelar reserva
                </button>
              )}
              <button className="btn btn-link" onClick={onClose}>
                Fechar
              </button>
            </div>
          </div>
        </div>
      </div>
      <div className="modal-backdrop fade show" />
    </>
  );
}

// ── Componentes de UI ───────────────────────────────────────────────────────
function StatCard({
  icon,
  value,
  label,
  color,
  loading,
}: {
  icon: React.ReactNode;
  value: number;
  label: string;
  color: string;
  loading: boolean;
}) {
  return (
    <div className="col-sm-4">
      <div className="card card-sm">
        <div className="card-body">
          <div className="row align-items-center">
            <div className="col-auto">
              <span className="avatar" style={{ backgroundColor: color, color: "#fff" }}>
                {icon}
              </span>
            </div>
            <div className="col">
              <div className="h1 mb-0 lh-1">
                {loading ? <span className="placeholder col-4" /> : value}
              </div>
              <div className="text-secondary">{label}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function LegendDot({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span className="d-inline-flex align-items-center me-3">
      <span
        className="d-inline-block me-1"
        style={{ width: 10, height: 10, borderRadius: 3, backgroundColor: color }}
      />
      <span className="text-secondary">{children}</span>
    </span>
  );
}

// ── Página ──────────────────────────────────────────────────────────────────
interface AgendaEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  kind: EventKind;
  sortKey: string;
}

export default function AgendaPage() {
  const { user } = useAuth();
  const assets = useAssets();
  // Bem selecionado vem da URL (?asset=<id>) → permite abrir a agenda de um bem por link.
  const [searchParams, setSearchParams] = useSearchParams();
  const asset = searchParams.get("asset") ?? "";
  const setAsset = (id: string) =>
    setSearchParams(id ? { asset: id } : {}, { replace: true });
  const bookings = useBookings(asset || undefined);
  const custodies = useCustodies({ asset: asset || undefined });
  const allCustodies = useCustodies(); // todas as cautelas → estado do bem no picker
  const allBookings = useBookings(); // todas as reservas → estado do bem no picker
  const [reserve, setReserve] = useState<{ start: string; end: string } | null>(null);
  const [detail, setDetail] = useState<Booking | null>(null);
  const [custodyFor, setCustodyFor] = useState<Booking | null>(null);
  const [filters, setFilters] = useState<Set<EventKind>>(
    () => new Set<EventKind>(["pending", "approved", "custody", "custody_pending"]),
  );

  const isManager = user?.roles.some((r) => r === "admin" || r === "director") ?? false;
  const loading = bookings.isLoading || custodies.isLoading;
  const assetLabel = assets.data?.results.find((a) => a.id === asset)?.name ?? "";

  // Fonte única de eventos (reservas + cautelas) memoizada.
  const allEvents = useMemo<AgendaEvent[]>(() => {
    const now = Date.now();
    const fromBookings = (bookings.data?.results ?? [])
      .filter((b) => b.status === "approved" || b.status === "pending")
      .map<AgendaEvent>((b) => {
        let kind: EventKind = "pending";
        if (b.status === "approved") {
          // Reserva aprovada cobrindo hoje = Cautelado (vermelho); futura = Aprovada (azul).
          const coversToday =
            new Date(b.start_at).getTime() <= now && now < new Date(b.end_at).getTime();
          kind = coversToday ? "custody" : "approved";
        }
        return { id: b.id, title: b.requester_name, start: b.start_at, end: b.end_at, kind, sortKey: b.start_at };
      });
    const fromCustodies = (custodies.data?.results ?? [])
      .filter((c) => c.status === "active" || c.status === "overdue" || c.status === "pending")
      .map<AgendaEvent>((c) => ({
        id: `custody-${c.id}`,
        title: c.holder_name,
        start: c.issued_at,
        end: `${addDays(c.due_at.slice(0, 10), 1)}T00:00:00`,
        kind: c.status === "pending" ? "custody_pending" : "custody",
        sortKey: c.issued_at,
      }));
    return [...fromBookings, ...fromCustodies];
  }, [bookings.data, custodies.data]);

  const visibleEvents = useMemo(
    () => allEvents.filter((e) => filters.has(e.kind)),
    [allEvents, filters],
  );

  const calendarEvents = useMemo(
    () =>
      visibleEvents.map((e) => {
        const color = KIND_META[e.kind].color;
        return {
          id: e.id,
          title: e.title,
          start: e.start,
          end: e.end,
          allDay: true,
          backgroundColor: color,
          borderColor: color,
          extendedProps: { kind: e.kind },
        };
      }),
    [visibleEvents],
  );

  const stats = useMemo(() => {
    const results = bookings.data?.results ?? [];
    const now = Date.now();
    const approved = results.filter((b) => b.status === "approved");
    const coversToday = (b: Booking) =>
      new Date(b.start_at).getTime() <= now && now < new Date(b.end_at).getTime();
    const activeCustody = (custodies.data?.results ?? []).filter(
      (c) => c.status === "active" || c.status === "overdue",
    ).length;
    return {
      pending: results.filter((b) => b.status === "pending").length,
      approved: approved.filter((b) => !coversToday(b)).length, // só futuras (azul)
      // Cautelado = cautela ativa + reserva aprovada acontecendo hoje
      custody: activeCustody + approved.filter(coversToday).length,
    };
  }, [bookings.data, custodies.data]);

  // Mapa bem → estado (cautela/reserva) para o seletor refletir a disponibilidade real.
  // Cautelado (vermelho) = ocupado HOJE (cautela ativa OU reserva cobrindo hoje).
  // Reserva aprovada futura = "Aprovada" (azul).
  const assetState = useMemo(() => {
    const rank: Record<AssetStateInfo["kind"], number> = {
      custody_active: 5,
      in_use: 4,
      custody_pending: 3,
      reserved: 2,
      booking_pending: 1,
    };
    const map: Record<string, AssetStateInfo> = {};
    const consider = (assetId: string, kind: AssetStateInfo["kind"], holder: string) => {
      const cur = map[assetId];
      if (!cur || rank[kind] > rank[cur.kind]) map[assetId] = { holder, kind };
    };
    for (const c of allCustodies.data?.results ?? []) {
      if (c.status === "active" || c.status === "overdue")
        consider(c.asset, "custody_active", c.holder_name);
      else if (c.status === "pending") consider(c.asset, "custody_pending", c.holder_name);
    }
    const now = Date.now();
    for (const b of allBookings.data?.results ?? []) {
      const startMs = new Date(b.start_at).getTime();
      const endMs = new Date(b.end_at).getTime();
      if (endMs < now) continue; // reserva já encerrada não ocupa o bem
      if (b.status === "approved") {
        const coversToday = startMs <= now && now < endMs;
        consider(b.asset, coversToday ? "in_use" : "reserved", b.requester_name);
      } else if (b.status === "pending") {
        consider(b.asset, "booking_pending", b.requester_name);
      }
    }
    return map;
  }, [allCustodies.data, allBookings.data]);

  // Lista "Próximas" — só reservas (clicáveis), ordenadas por início.
  const upcoming = useMemo(
    () =>
      visibleEvents
        .filter((e) => e.kind === "pending" || e.kind === "approved")
        .slice()
        .sort((a, b) => a.sortKey.localeCompare(b.sortKey)),
    [visibleEvents],
  );

  function toggleFilter(kind: EventKind) {
    setFilters((prev) => {
      const next = new Set(prev);
      if (next.has(kind)) next.delete(kind);
      else next.add(kind);
      return next;
    });
  }

  function openBookingDetail(id: string) {
    const b = bookings.data?.results.find((x) => x.id === id);
    if (b) setDetail(b);
  }

  return (
    <>
      <style>{`
        .fc .fc-daygrid-event { border-radius: 6px; padding: 1px 4px; font-weight: 500; }
        .fc .fc-event:hover { filter: brightness(0.94); cursor: pointer; }
        .fc .fc-toolbar-title { font-size: 1.05rem; font-weight: 600; }
        .fc .fc-day-today { background: rgba(32,107,196,.06) !important; }
        .agenda-filter { cursor: pointer; user-select: none; transition: opacity .15s; }
        .agenda-filter.is-off { opacity: .4; }
        .agenda-upcoming-item { cursor: pointer; }
        .agenda-upcoming-item:hover { background: var(--tblr-active-bg, #f1f5f9); }
      `}</style>

      <div className="page-header d-print-none">
        <div className="row align-items-center g-2">
          <div className="col">
            <div className="page-pretitle">Reservas &amp; Cautelas</div>
            <h2 className="page-title">
              <IconCalendarEvent className="icon me-2" />
              Agenda
            </h2>
          </div>
          <div className="col-12 col-md-auto ms-md-auto">
            <AssetPicker
              assets={assets.data?.results ?? []}
              value={asset}
              onChange={setAsset}
              state={assetState}
            />
          </div>
        </div>
      </div>

      {!asset && (
        <div className="card mt-3">
          <div className="card-body">
            <div className="empty">
              <div className="empty-icon">
                <IconCalendarEvent size={48} className="text-secondary" />
              </div>
              <p className="empty-title">Selecione um bem</p>
              <p className="empty-subtitle text-secondary">
                Escolha um bem acima para ver suas reservas e cautelas. Clique em um intervalo de
                dias no calendário para criar uma nova reserva.
              </p>
            </div>
          </div>
        </div>
      )}

      {asset && (
        <>
          <div className="row row-cards mt-1">
            <StatCard
              icon={<IconClock size={22} />}
              value={stats.pending}
              label="Pendentes"
              color={PENDING}
              loading={loading}
            />
            <StatCard
              icon={<IconClipboardCheck size={22} />}
              value={stats.approved}
              label="Aprovadas"
              color={APPROVED}
              loading={loading}
            />
            <StatCard
              icon={stats.custody > 0 ? <IconAlertTriangle size={22} /> : <IconPackage size={22} />}
              value={stats.custody}
              label="Cautelado"
              color={CUSTODY}
              loading={loading}
            />
          </div>

          <div className="row row-cards mt-1">
            <div className="col-12 col-xl-8">
              <div className="card">
                <div className="card-header d-flex flex-wrap align-items-center gap-2">
                  <div className="d-flex flex-wrap">
                    {(Object.keys(KIND_META) as EventKind[]).map((kind) => (
                      <span
                        key={kind}
                        className={`agenda-filter${filters.has(kind) ? "" : " is-off"}`}
                        onClick={() => toggleFilter(kind)}
                        title="Mostrar/ocultar"
                      >
                        <LegendDot color={KIND_META[kind].color}>
                          {KIND_META[kind].label}
                        </LegendDot>
                      </span>
                    ))}
                  </div>
                  <span className="text-secondary small ms-auto d-none d-sm-inline">
                    Arraste sobre os dias para reservar
                  </span>
                </div>
                <div className="card-body">
                  <FullCalendar
                    plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
                    initialView="dayGridMonth"
                    locale={ptBrLocale}
                    headerToolbar={{
                      left: "prev,next today",
                      center: "title",
                      right: "dayGridMonth,dayGridWeek",
                    }}
                    height="70vh"
                    fixedWeekCount={false}
                    dayMaxEventRows={3}
                    selectable
                    selectMirror
                    // Bloqueia selecionar dias no passado ou já ocupados (reserva/cautela).
                    selectAllow={(span) => {
                      if (span.start < new Date(new Date().setHours(0, 0, 0, 0))) return false;
                      const s = span.start.getTime();
                      const e = span.end.getTime();
                      return !allEvents.some((ev) => {
                        const es = new Date(ev.start).getTime();
                        const ee = new Date(ev.end).getTime();
                        return s < ee && e > es; // sobreposição de intervalos
                      });
                    }}
                    select={(info) =>
                      setReserve({
                        start: dateStr(info.start),
                        // FullCalendar entrega fim exclusivo; converto p/ dia inclusivo
                        end: addDays(dateStr(info.end), -1),
                      })
                    }
                    eventClick={(info) => {
                      // cautelas têm id "custody-…" e não abrem detalhe de reserva
                      if (info.event.id.startsWith("custody-")) return;
                      openBookingDetail(info.event.id);
                    }}
                    eventContent={(arg) => (
                      <div className="d-flex align-items-center gap-1 text-truncate px-1">
                        <span className="fw-bold">•</span>
                        <span className="text-truncate">{arg.event.title}</span>
                      </div>
                    )}
                    events={calendarEvents}
                  />
                </div>
              </div>
            </div>

            <div className="col-12 col-xl-4">
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">Próximas reservas</h3>
                </div>
                {loading ? (
                  <div className="card-body">
                    <div className="placeholder-glow">
                      <div className="placeholder col-12 mb-2" />
                      <div className="placeholder col-9 mb-2" />
                      <div className="placeholder col-10" />
                    </div>
                  </div>
                ) : upcoming.length === 0 ? (
                  <div className="card-body text-secondary text-center py-4">
                    Nenhuma reserva no período.
                  </div>
                ) : (
                  <div className="list-group list-group-flush">
                    {upcoming.map((e) => (
                      <button
                        key={e.id}
                        type="button"
                        className="list-group-item list-group-item-action agenda-upcoming-item d-flex align-items-center"
                        onClick={() => openBookingDetail(e.id)}
                      >
                        <span
                          className="me-2 flex-shrink-0"
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            backgroundColor: KIND_META[e.kind].color,
                          }}
                        />
                        <div className="flex-fill text-truncate">
                          <div className="text-truncate fw-medium">{e.title}</div>
                          <div className="text-secondary small">
                            {fmtDate(e.start)} · {relativeDay(e.start)}
                          </div>
                        </div>
                        <span
                          className="badge me-2"
                          style={{ backgroundColor: KIND_META[e.kind].color, color: "#fff" }}
                        >
                          {KIND_META[e.kind].label}
                        </span>
                        <IconChevronRight size={16} className="text-secondary" />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {reserve && asset && (
        <BookingModal
          asset={asset}
          initialStart={reserve.start}
          initialEnd={reserve.end}
          onClose={() => setReserve(null)}
        />
      )}
      {detail && (
        <BookingDetailModal
          booking={detail}
          isManager={isManager}
          onEmitCustody={(b) => {
            setDetail(null);
            setCustodyFor(b);
          }}
          onClose={() => setDetail(null)}
        />
      )}
      {custodyFor && (
        <IssueCustodyModal
          asset={custodyFor.asset}
          assetLabel={assetLabel}
          defaultHolder={custodyFor.requester}
          // end_at é exclusivo (dia seguinte 00:00) → último dia da reserva = -1 dia
          defaultDue={addDays(custodyFor.end_at.slice(0, 10), -1)}
          bookingId={custodyFor.id}
          onClose={() => setCustodyFor(null)}
        />
      )}
    </>
  );
}
