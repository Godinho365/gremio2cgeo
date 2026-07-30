import ptBrLocale from "@fullcalendar/core/locales/pt-br";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import { useMemo, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import { useAssets } from "../features/assets/api";
import {
  useAvailabilities,
  useBookings,
  useCreateAvailability,
  useCreateBooking,
} from "../features/scheduling/api";

const RED = "#d63939"; // ocupado (aprovada)
const ORANGE = "#f76707"; // pendente
const GREEN = "#2fb344"; // disponível

const WEEKDAYS = [
  "Segunda",
  "Terça",
  "Quarta",
  "Quinta",
  "Sexta",
  "Sábado",
  "Domingo",
];

// backend weekday (0=Seg..6=Dom) -> FullCalendar (0=Dom..6=Sáb)
const toFcDay = (w: number) => (w + 1) % 7;

function toLocalInput(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(
    d.getMinutes(),
  )}`;
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
      await create.mutateAsync({ asset, start_at: start, end_at: end });
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
                  <div className="col-md-6 mb-3">
                    <label className="form-label required">Início</label>
                    <input
                      type="datetime-local"
                      className="form-control"
                      value={start}
                      onChange={(e) => setStart(e.target.value)}
                      required
                    />
                  </div>
                  <div className="col-md-6 mb-3">
                    <label className="form-label required">Término</label>
                    <input
                      type="datetime-local"
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
  const [start, setStart] = useState("08:00");
  const [end, setEnd] = useState("18:00");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    await create.mutateAsync({
      asset,
      weekday,
      start_time: `${start}:00`,
      end_time: `${end}:00`,
    });
    onClose();
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Definir disponibilidade</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                <div className="mb-3">
                  <label className="form-label">Dia da semana</label>
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
                <div className="row">
                  <div className="col-6 mb-2">
                    <label className="form-label">Das</label>
                    <input
                      type="time"
                      className="form-control"
                      value={start}
                      onChange={(e) => setStart(e.target.value)}
                    />
                  </div>
                  <div className="col-6 mb-2">
                    <label className="form-label">Até</label>
                    <input
                      type="time"
                      className="form-control"
                      value={end}
                      onChange={(e) => setEnd(e.target.value)}
                    />
                  </div>
                </div>
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

export default function AgendaPage() {
  const { user } = useAuth();
  const assets = useAssets();
  const [asset, setAsset] = useState("");
  const bookings = useBookings(asset || undefined);
  const availabilities = useAvailabilities(asset || undefined);
  const [reserve, setReserve] = useState<{ start: string; end: string } | null>(null);
  const [showAvail, setShowAvail] = useState(false);

  const isManager = user?.roles.some((r) => r === "admin" || r === "director") ?? false;

  const events = useMemo(() => {
    const busy = (bookings.data?.results ?? [])
      .filter((b) => b.status === "approved" || b.status === "pending")
      .map((b) => ({
        id: b.id,
        title: `${b.requester_name} (${b.status === "approved" ? "aprovada" : "pendente"})`,
        start: b.start_at,
        end: b.end_at,
        backgroundColor: b.status === "approved" ? RED : ORANGE,
        borderColor: b.status === "approved" ? RED : ORANGE,
      }));
    const green = (availabilities.data ?? []).map((a) => ({
      daysOfWeek: [toFcDay(a.weekday)],
      startTime: a.start_time.slice(0, 5),
      endTime: a.end_time.slice(0, 5),
      display: "background" as const,
      backgroundColor: GREEN,
    }));
    return [...green, ...busy];
  }, [bookings.data, availabilities.data]);

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
              <button className="btn btn-outline-success me-2" onClick={() => setShowAvail(true)}>
                + Disponibilidade
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
                A agenda mostra em <strong>verde</strong> quando o bem pode ser cautelado e em{" "}
                <strong>vermelho</strong> os períodos já ocupados.
              </p>
            </div>
          )}

          {asset && (
            <FullCalendar
              plugins={[timeGridPlugin, dayGridPlugin, interactionPlugin]}
              initialView="timeGridWeek"
              locale={ptBrLocale}
              headerToolbar={{
                left: "prev,next today",
                center: "title",
                right: "dayGridMonth,timeGridWeek,timeGridDay",
              }}
              height="70vh"
              nowIndicator
              selectable
              selectMirror
              select={(info) =>
                setReserve({
                  start: toLocalInput(info.start),
                  end: toLocalInput(info.end),
                })
              }
              events={events}
              slotMinTime="06:00:00"
              slotMaxTime="22:00:00"
              allDaySlot={false}
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
    </>
  );
}
