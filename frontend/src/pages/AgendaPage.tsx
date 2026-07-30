import ptBrLocale from "@fullcalendar/core/locales/pt-br";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";
import FullCalendar from "@fullcalendar/react";
import { useMemo, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import IssueCustodyModal from "../components/IssueCustodyModal";
import { useAssets } from "../features/assets/api";
import { useCustodies } from "../features/custody/api";
import {
  type Booking,
  useApproveBooking,
  useAvailabilities,
  useBookings,
  useCancelBooking,
  useCreateAvailability,
  useCreateBooking,
} from "../features/scheduling/api";

const RED = "#d63939"; // ocupado (aprovada)
const ORANGE = "#f76707"; // pendente
const GREEN = "#2fb344"; // disponível

const WEEKDAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];

// backend weekday (0=Seg..6=Dom) -> FullCalendar (0=Dom..6=Sáb)
const toFcDay = (w: number) => (w + 1) % 7;

const pad = (n: number) => String(n).padStart(2, "0");
const dateStr = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return dateStr(d);
}

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
  const [start, setStart] = useState(initialStart);
  const [end, setEnd] = useState(initialEnd);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
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
                      className="form-control"
                      value={start}
                      onChange={(e) => setStart(e.target.value)}
                      required
                    />
                  </div>
                  <div className="col-6 mb-3">
                    <label className="form-label required">Até</label>
                    <input
                      type="date"
                      className="form-control"
                      value={end}
                      onChange={(e) => setEnd(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={create.isPending}>
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

function AvailabilityModal({ asset, onClose }: { asset: string; onClose: () => void }) {
  const create = useCreateAvailability();
  const [weekday, setWeekday] = useState(0);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    // Dia inteiro disponível (sem horas).
    await create.mutateAsync({
      asset,
      weekday,
      start_time: "00:00:00",
      end_time: "23:59:59",
    });
    onClose();
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered modal-sm">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Dia disponível</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                <label className="form-label">Dia da semana disponível para cautela</label>
                <select
                  className="form-select"
                  value={weekday}
                  onChange={(e) => setWeekday(Number(e.target.value))}
                >
                  {WEEKDAYS.map((d, i) => (
                    <option key={i} value={i}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-success" disabled={create.isPending}>
                  Adicionar
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

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR");
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

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
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
                <dd className="col-8">{booking.status}</dd>
              </dl>
            </div>
            <div className="modal-footer">
              {isManager && booking.status === "pending" && (
                <button
                  className="btn btn-success"
                  onClick={() => approve.mutate(booking.id, { onSuccess: onClose })}
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

export default function AgendaPage() {
  const { user } = useAuth();
  const assets = useAssets();
  const [asset, setAsset] = useState("");
  const bookings = useBookings(asset || undefined);
  const availabilities = useAvailabilities(asset || undefined);
  const custodies = useCustodies(asset || undefined);
  const [reserve, setReserve] = useState<{ start: string; end: string } | null>(null);
  const [showAvail, setShowAvail] = useState(false);
  const [detail, setDetail] = useState<Booking | null>(null);
  const [custodyFor, setCustodyFor] = useState<Booking | null>(null);

  const isManager = user?.roles.some((r) => r === "admin" || r === "director") ?? false;
  const assetLabel =
    assets.data?.results.find((a) => a.id === asset)?.name ?? "";

  const events = useMemo(() => {
    const busy = (bookings.data?.results ?? [])
      .filter((b) => b.status === "approved" || b.status === "pending")
      .map((b) => ({
        id: b.id,
        title: `${b.requester_name} (${b.status === "approved" ? "aprovada" : "pendente"})`,
        start: b.start_at,
        end: b.end_at,
        allDay: true,
        backgroundColor: b.status === "approved" ? RED : ORANGE,
        borderColor: b.status === "approved" ? RED : ORANGE,
      }));
    // cautelas ativas/atrasadas = bem em uso (vermelho, do dia da emissão ao prazo)
    const custodied = (custodies.data?.results ?? [])
      .filter((c) => c.status === "active" || c.status === "overdue")
      .map((c) => ({
        id: `custody-${c.id}`,
        title: `Cautelado — ${c.holder_name}`,
        start: c.issued_at,
        end: addDays(c.due_at.slice(0, 10), 1),
        allDay: true,
        backgroundColor: RED,
        borderColor: RED,
      }));
    // verde = dias da semana disponíveis para cautelar (pinta a célula do dia)
    const green = (availabilities.data ?? []).map((a) => ({
      daysOfWeek: [toFcDay(a.weekday)],
      display: "background" as const,
      backgroundColor: GREEN,
    }));
    return [...green, ...busy, ...custodied];
  }, [bookings.data, availabilities.data, custodies.data]);

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <h2 className="page-title">Agenda</h2>
            <div className="text-secondary mt-1">
              <span className="badge me-1" style={{ backgroundColor: GREEN }}>
                &nbsp;
              </span>
              Disponível para cautelar &nbsp;·&nbsp;
              <span className="badge me-1" style={{ backgroundColor: RED }}>
                &nbsp;
              </span>
              Ocupado
            </div>
          </div>
          <div className="col-auto ms-auto">
            {isManager && asset && (
              <button className="btn btn-outline-success" onClick={() => setShowAvail(true)}>
                + Dia disponível
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="card mt-3">
        <div className="card-body">
          <div className="mb-3" style={{ maxWidth: 420 }}>
            <label className="form-label">Bem</label>
            <select
              className="form-select"
              value={asset}
              onChange={(e) => setAsset(e.target.value)}
            >
              <option value="">Selecione um bem para ver a agenda…</option>
              {assets.data?.results.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.asset_tag} — {a.name}
                </option>
              ))}
            </select>
          </div>

          {!asset && (
            <div className="empty">
              <p className="empty-title">Selecione um bem</p>
              <p className="empty-subtitle text-secondary">
                A agenda mostra em <strong>verde</strong> os dias em que o bem pode ser cautelado e
                em <strong>vermelho</strong> os dias já ocupados.
              </p>
            </div>
          )}

          {asset && (
            <FullCalendar
              plugins={[dayGridPlugin, interactionPlugin]}
              initialView="dayGridMonth"
              locale={ptBrLocale}
              headerToolbar={{
                left: "prev,next today",
                center: "title",
                right: "dayGridMonth,dayGridWeek",
              }}
              height="72vh"
              selectable
              select={(info) =>
                setReserve({
                  start: dateStr(info.start),
                  // FullCalendar entrega fim exclusivo; converto p/ dia inclusivo
                  end: addDays(dateStr(info.end), -1),
                })
              }
              eventClick={(info) => {
                const b = bookings.data?.results.find((x) => x.id === info.event.id);
                if (b) setDetail(b);
              }}
              events={events}
            />
          )}
        </div>
      </div>

      {reserve && asset && (
        <BookingModal
          asset={asset}
          initialStart={reserve.start}
          initialEnd={reserve.end}
          onClose={() => setReserve(null)}
        />
      )}
      {showAvail && asset && (
        <AvailabilityModal asset={asset} onClose={() => setShowAvail(false)} />
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
          bookingId={custodyFor.id}
          onClose={() => setCustodyFor(null)}
        />
      )}
    </>
  );
}
