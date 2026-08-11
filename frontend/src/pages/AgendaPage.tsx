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
  IconSearch,
} from "@tabler/icons-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import AssetPicker, {
  type AssetStateInfo,
  STATE_META as PICKER_STATE,
} from "../components/AssetPicker";
import IssueCustodyModal from "../components/IssueCustodyModal";
import Pagination from "../components/Pagination";
import ReturnCustodyModal from "../components/ReturnCustodyModal";
import { MILITARY_RANKS, useCreateUser, useUsers } from "../features/accounts/api";
import { useAssets, useCategories } from "../features/assets/api";
import {
  CUSTODY_STATUS,
  type Custody,
  useApproveCustody,
  useCustodies,
  useRejectCustody,
} from "../features/custody/api";
import {
  type Booking,
  useApproveBooking,
  useBookings,
  useCancelBooking,
  useCreateBooking,
  useDeleteBooking,
} from "../features/scheduling/api";
import { addDays, dateStr } from "../lib/dates";

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

/** Valor sentinela do seletor "Reservar para" que abre o cadastro sem acesso. */
const NEW_GUEST = "__novo__";

/** Bens por página na lista de escolha. */
const POR_PAGINA = 7;

// ── Modais ──────────────────────────────────────────────────────────────────
function BookingModal({
  asset,
  initialStart,
  initialEnd,
  isManager,
  onClose,
}: {
  asset: string;
  initialStart: string;
  initialEnd: string;
  /** Gestor pode reservar em nome de outro usuário. */
  isManager: boolean;
  onClose: () => void;
}) {
  const create = useCreateBooking();
  const createUser = useCreateUser();
  const users = useUsers();
  const today = dateStr(new Date());
  const [start, setStart] = useState(initialStart);
  const [end, setEnd] = useState(initialEnd);
  const [requester, setRequester] = useState(""); // vazio = para si mesmo
  // Pessoa sem acesso: cadastro criado na hora, só para constar na reserva/cautela.
  const [guest, setGuest] = useState({ full_name: "", posto_graduacao: "", nome_guerra: "" });
  const [error, setError] = useState<string | null>(null);
  const isGuest = requester === NEW_GUEST;

  const startPast = start !== "" && start < today; // início no passado
  const endBeforeStart = end !== "" && start !== "" && end < start; // término antes do início
  const guestMissingName = isGuest && !guest.full_name.trim();
  const invalid = !start || !end || startPast || endBeforeStart || guestMissingName;

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
      let requesterId = isGuest ? "" : requester;
      if (isGuest) {
        const created = await createUser.mutateAsync({
          is_active: false, // sem login: existe só para constar
          full_name: guest.full_name.trim(),
          nome_guerra: guest.nome_guerra.trim(),
          posto_graduacao: guest.posto_graduacao,
          role_codes: ["user"],
        });
        requesterId = created.id;
      }
      // datas inclusivas -> intervalo meio-aberto [start 00:00, (end+1) 00:00)
      await create.mutateAsync({
        asset,
        start_at: `${start}T00:00:00`,
        end_at: `${addDays(end, 1)}T00:00:00`,
        ...(requesterId ? { requester: requesterId } : {}),
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
                {isManager && (
                  <div className="mb-3">
                    <label className="form-label">Reservar para</label>
                    <select
                      className="form-select"
                      value={requester}
                      onChange={(e) => setRequester(e.target.value)}
                    >
                      <option value="">Eu mesmo</option>
                      {users.data?.map((u) => (
                        <option key={u.id} value={u.id}>
                          {u.display_name}
                          {u.is_active ? "" : " (sem acesso)"}
                        </option>
                      ))}
                      <option value={NEW_GUEST}>＋ Cadastrar pessoa sem acesso…</option>
                    </select>
                    {isGuest ? (
                      <div className="card card-sm mt-2">
                        <div className="card-body">
                          <div className="mb-2">
                            <label className="form-label required">Nome completo</label>
                            <input
                              className="form-control"
                              value={guest.full_name}
                              onChange={(e) =>
                                setGuest((g) => ({ ...g, full_name: e.target.value }))
                              }
                              required
                            />
                          </div>
                          <div className="row">
                            <div className="col-5">
                              <label className="form-label">Posto/Grad.</label>
                              <select
                                className="form-select"
                                value={guest.posto_graduacao}
                                onChange={(e) =>
                                  setGuest((g) => ({ ...g, posto_graduacao: e.target.value }))
                                }
                              >
                                <option value="">—</option>
                                {MILITARY_RANKS.map((grp) => (
                                  <optgroup key={grp.group} label={grp.group}>
                                    {grp.items.map((r) => (
                                      <option key={r.value} value={r.value}>
                                        {r.label} ({r.value})
                                      </option>
                                    ))}
                                  </optgroup>
                                ))}
                              </select>
                            </div>
                            <div className="col-7">
                              <label className="form-label">Nome de guerra</label>
                              <input
                                className="form-control"
                                placeholder="SILVA"
                                value={guest.nome_guerra}
                                onChange={(e) =>
                                  setGuest((g) => ({
                                    ...g,
                                    nome_guerra: e.target.value.toUpperCase(),
                                  }))
                                }
                              />
                            </div>
                          </div>
                          <small className="form-hint mt-2 d-block">
                            Cadastro sem login nem senha: serve para constar na reserva e na
                            cautela.
                          </small>
                        </div>
                      </div>
                    ) : (
                      <small className="form-hint">
                        A reserva fica no nome do usuário escolhido.
                      </small>
                    )}
                  </div>
                )}
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
                  disabled={create.isPending || createUser.isPending || invalid}
                >
                  {create.isPending || createUser.isPending ? "Salvando…" : "Reservar"}
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
  custody,
  isManager,
  isOwner,
  onEmitCustody,
  onReturnCustody,
  onClose,
}: {
  booking: Booking;
  /** Cautela do bem em aberto (solicitada/ativa/atrasada), quando houver. */
  custody: Custody | null;
  isManager: boolean;
  /** Quem abriu a reserva pode cancelá-la; aprovar é só do gestor. */
  isOwner: boolean;
  onEmitCustody: (b: Booking) => void;
  onReturnCustody: (c: Custody) => void;
  onClose: () => void;
}) {
  const approve = useApproveBooking();
  const approveCustody = useApproveCustody();
  const cancel = useCancelBooking();
  const remove = useDeleteBooking();
  const active = booking.status === "pending" || booking.status === "approved";
  const issued = custody?.status === "active" || custody?.status === "overdue";
  const meta = issued
    ? KIND_META.custody
    : custody?.status === "pending"
      ? KIND_META.custody_pending
      : booking.status === "approved"
        ? KIND_META.approved
        : KIND_META.pending;

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
                {custody && (
                  <>
                    <dt className="col-4">Cautelado com</dt>
                    <dd className="col-8">{custody.holder_name}</dd>
                    <dt className="col-4">Devolver até</dt>
                    <dd className="col-8">{fmtDate(custody.due_at)}</dd>
                  </>
                )}
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
              {/* Bem já cautelado: o que resta ao gestor é registrar a entrega (condição + descrição). */}
              {isManager && issued && custody && (
                <button className="btn btn-primary" onClick={() => onReturnCustody(custody)}>
                  Registrar entrega
                </button>
              )}
              {isManager && custody?.status === "pending" && (
                <button
                  className="btn btn-success"
                  onClick={() => approveCustody.mutate(custody.id, { onSuccess: onClose })}
                  disabled={approveCustody.isPending}
                >
                  Aprovar cautela
                </button>
              )}
              {isManager && !custody && booking.status === "approved" && (
                <button className="btn btn-primary" onClick={() => onEmitCustody(booking)}>
                  Entregar
                </button>
              )}
              {active && (isManager || isOwner) && (
                <button
                  className="btn btn-ghost-danger"
                  onClick={() => cancel.mutate(booking.id, { onSuccess: onClose })}
                  disabled={cancel.isPending}
                >
                  Cancelar reserva
                </button>
              )}
              {isManager && (
                <button
                  className="btn btn-ghost-danger"
                  onClick={() => {
                    if (confirm("Excluir esta reserva do histórico?"))
                      remove.mutate(booking.id, { onSuccess: onClose });
                  }}
                  disabled={remove.isPending}
                >
                  Excluir
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

function CustodyDetailModal({
  custody,
  isManager,
  onReturnCustody,
  onClose,
}: {
  custody: Custody;
  isManager: boolean;
  onReturnCustody: (c: Custody) => void;
  onClose: () => void;
}) {
  const approve = useApproveCustody();
  const reject = useRejectCustody();
  const open = custody.status === "active" || custody.status === "overdue";
  const meta = open ? KIND_META.custody : KIND_META.custody_pending;

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-status" style={{ backgroundColor: meta.color }} />
            <div className="modal-header">
              <h5 className="modal-title">Cautela — {custody.asset_name}</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <div className="modal-body">
              <dl className="row mb-0">
                <dt className="col-4">Responsável</dt>
                <dd className="col-8">{custody.holder_name}</dd>
                <dt className="col-4">Cautelado em</dt>
                <dd className="col-8">{fmtDate(custody.issued_at)}</dd>
                <dt className="col-4">Devolver até</dt>
                <dd className="col-8">{fmtDate(custody.due_at)}</dd>
                <dt className="col-4">Situação</dt>
                <dd className="col-8">
                  <span className="badge" style={{ backgroundColor: meta.color, color: "#fff" }}>
                    {CUSTODY_STATUS[custody.status].label}
                  </span>
                </dd>
              </dl>
            </div>
            <div className="modal-footer">
              {isManager && open && (
                <button className="btn btn-primary" onClick={() => onReturnCustody(custody)}>
                  Registrar entrega
                </button>
              )}
              {isManager && custody.status === "pending" && (
                <>
                  <button
                    className="btn btn-success"
                    onClick={() => approve.mutate(custody.id, { onSuccess: onClose })}
                    disabled={approve.isPending}
                  >
                    Aprovar cautela
                  </button>
                  <button
                    className="btn btn-ghost-secondary"
                    onClick={() => reject.mutate(custody.id, { onSuccess: onClose })}
                    disabled={reject.isPending}
                  >
                    Rejeitar
                  </button>
                </>
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
  /** Gestor abre qualquer uma; o usuário comum, só as próprias. */
  canOpen: boolean;
}

export default function AgendaPage() {
  const { user } = useAuth();
  // Busca e tipo filtram no servidor; o seletor e a lista de escolha usam o
  // mesmo recorte, então o que se procura é o que se vê.
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [assetPage, setAssetPage] = useState(1);
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(qInput);
      setAssetPage(1);
    }, 350);
    return () => clearTimeout(t);
  }, [qInput]);

  const categories = useCategories();
  const assets = useAssets({
    q: q || undefined,
    category: category || undefined,
    pageSize: 200, // o seletor precisa da lista inteira, não da primeira página
  });
  // Bem selecionado vem da URL (?asset=<id>) → permite abrir a agenda de um bem por link.
  const [searchParams, setSearchParams] = useSearchParams();
  const asset = searchParams.get("asset") ?? "";
  const setAsset = (id: string) =>
    setSearchParams(id ? { asset: id } : {}, { replace: true });
  const bookings = useBookings({ asset: asset || undefined });
  const custodies = useCustodies({ asset: asset || undefined });
  const allCustodies = useCustodies(); // todas as cautelas → estado do bem no picker
  const allBookings = useBookings(); // todas as reservas → estado do bem no picker
  const [reserve, setReserve] = useState<{ start: string; end: string } | null>(null);
  const [detail, setDetail] = useState<Booking | null>(null);
  const [custodyDetail, setCustodyDetail] = useState<Custody | null>(null);
  const [returning, setReturning] = useState<Custody | null>(null);
  const [custodyFor, setCustodyFor] = useState<Booking | null>(null);
  const [filters, setFilters] = useState<Set<EventKind>>(
    () => new Set<EventKind>(["pending", "approved", "custody", "custody_pending"]),
  );

  // A lista de escolha pagina localmente: os bens filtrados já vieram todos.
  const assetsFiltrados = assets.data?.results ?? [];
  const totalPaginas = Math.max(1, Math.ceil(assetsFiltrados.length / POR_PAGINA));
  const paginaAtual = Math.min(assetPage, totalPaginas);
  const assetsNaPagina = assetsFiltrados.slice(
    (paginaAtual - 1) * POR_PAGINA,
    paginaAtual * POR_PAGINA,
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
        return {
          id: b.id,
          title: b.requester_name,
          start: b.start_at,
          end: b.end_at,
          kind,
          sortKey: b.start_at,
          canOpen: isManager || b.requester === user?.id,
        };
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
        canOpen: isManager || c.holder === user?.id,
      }));
    return [...fromBookings, ...fromCustodies];
  }, [bookings.data, custodies.data, isManager, user?.id]);

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
          classNames: e.canOpen ? [] : ["agenda-event-locked"],
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

  // Só o gestor e o dono abrem o detalhe: reserva de outra pessoa não se mexe.
  const ownsBooking = (b: Booking) => b.requester === user?.id;
  const ownsCustody = (c: Custody) => c.holder === user?.id;

  function openBookingDetail(id: string) {
    const b = bookings.data?.results.find((x) => x.id === id);
    if (b && (isManager || ownsBooking(b))) setDetail(b);
  }

  function openCustodyDetail(eventId: string) {
    const id = eventId.replace("custody-", "");
    const c = custodies.data?.results.find((x) => x.id === id);
    if (c && (isManager || ownsCustody(c))) setCustodyDetail(c);
  }

  /** Cautela em aberto do bem da reserva (solicitada/ativa/atrasada); a da própria reserva tem prioridade. */
  function openCustodyFor(b: Booking): Custody | null {
    const candidates = (custodies.data?.results ?? []).filter(
      (c) =>
        (c.status === "pending" || c.status === "active" || c.status === "overdue") &&
        (c.booking === b.id || c.asset === b.asset),
    );
    return candidates.find((c) => c.booking === b.id) ?? candidates[0] ?? null;
  }

  return (
    <>
      <style>{`
        .fc .fc-daygrid-event { border-radius: 6px; padding: 1px 4px; font-weight: 500; }
        .fc .fc-event:hover { filter: brightness(0.94); cursor: pointer; }
        .fc .fc-event.agenda-event-locked:hover { filter: none; cursor: default; }
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

      {/* Busca e tipo: filtram o seletor e a lista de escolha ao mesmo tempo. */}
      <div className="card mt-3">
        <div className="card-body py-2">
          <div className="row g-2 align-items-center">
            <div className="col-12 col-md">
              <div className="input-icon">
                <span className="input-icon-addon">
                  <IconSearch size={16} />
                </span>
                <input
                  className="form-control"
                  placeholder="Buscar bem pelo nome ou número…"
                  value={qInput}
                  onChange={(e) => setQInput(e.target.value)}
                />
              </div>
            </div>
            <div className="col-auto">
              <select
                className="form-select"
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value);
                  setAssetPage(1);
                }}
              >
                <option value="">Todos os tipos</option>
                {categories.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            {(q || category || asset) && (
              <div className="col-auto">
                <button
                  className="btn btn-link"
                  onClick={() => {
                    setQInput("");
                    setQ("");
                    setCategory("");
                    setAsset("");
                    setAssetPage(1);
                  }}
                >
                  Limpar
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {!asset && (
        <div className="card mt-3">
          <div className="card-header">
            <h3 className="card-title">Escolha um bem para ver a agenda</h3>
            <span className="card-actions text-secondary small">
              {assets.data?.count ?? 0} {(assets.data?.count ?? 0) === 1 ? "bem" : "bens"}
            </span>
          </div>
          {assets.isLoading ? (
            <div className="card-body text-secondary">Carregando…</div>
          ) : (assets.data?.results.length ?? 0) === 0 ? (
            <div className="card-body text-secondary text-center py-4">
              Nenhum bem para esse filtro.
            </div>
          ) : (
            <div className="list-group list-group-flush">
              {assetsNaPagina.map((a) => {
                const info = assetState[a.id];
                const meta = info ? PICKER_STATE[info.kind] : null;
                return (
                  <button
                    key={a.id}
                    type="button"
                    className="list-group-item list-group-item-action d-flex align-items-center gap-2"
                    onClick={() => setAsset(a.id)}
                  >
                    <span className="flex-fill text-truncate">
                      <span className="d-block text-truncate fw-medium">{a.name}</span>
                      <span className="asset-tag">{a.asset_tag}</span>
                      {a.category_name && (
                        <span className="text-secondary small"> · {a.category_name}</span>
                      )}
                    </span>
                    {meta && info ? (
                      <span className={`badge ${meta.badge}`}>
                        {meta.label} · {info.holder}
                      </span>
                    ) : (
                      <span className="badge bg-green-lt">Livre</span>
                    )}
                    <IconChevronRight size={16} className="text-secondary" />
                  </button>
                );
              })}
            </div>
          )}
          {assetsFiltrados.length > POR_PAGINA && (
            <Pagination
              page={paginaAtual}
              count={assetsFiltrados.length}
              label={{ one: "bem", many: "bens" }}
              pageSize={POR_PAGINA}
              onChange={setAssetPage}
            />
          )}
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
                      // cautelas têm id "custody-…" e abrem o detalhe da cautela
                      if (info.event.id.startsWith("custody-")) {
                        openCustodyDetail(info.event.id);
                        return;
                      }
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
                        className={`list-group-item d-flex align-items-center${
                          e.canOpen ? " list-group-item-action agenda-upcoming-item" : ""
                        }`}
                        style={e.canOpen ? undefined : { cursor: "default" }}
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
                        {e.canOpen && <IconChevronRight size={16} className="text-secondary" />}
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
          isManager={isManager}
          onClose={() => setReserve(null)}
        />
      )}
      {detail && (
        <BookingDetailModal
          booking={detail}
          custody={openCustodyFor(detail)}
          isManager={isManager}
          isOwner={ownsBooking(detail)}
          onEmitCustody={(b) => {
            setDetail(null);
            setCustodyFor(b);
          }}
          onReturnCustody={(c) => {
            setDetail(null);
            setReturning(c);
          }}
          onClose={() => setDetail(null)}
        />
      )}
      {custodyDetail && (
        <CustodyDetailModal
          custody={custodyDetail}
          isManager={isManager}
          onReturnCustody={(c) => {
            setCustodyDetail(null);
            setReturning(c);
          }}
          onClose={() => setCustodyDetail(null)}
        />
      )}
      {returning && (
        <ReturnCustodyModal custody={returning} onClose={() => setReturning(null)} />
      )}
      {custodyFor && (
        <IssueCustodyModal
          asset={custodyFor.asset}
          assetLabel={assetLabel}
          defaultHolder={custodyFor.requester}
          // entrega no primeiro dia da reserva (o modal limita a hoje)
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
