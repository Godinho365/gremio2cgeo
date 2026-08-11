import {
  IconCalendarEvent,
  IconCheck,
  IconCurrencyReal,
  IconScissors,
  IconTicket,
  IconX,
} from "@tabler/icons-react";
import { useEffect, useMemo, useRef, useState } from "react";

import Pagination from "../components/Pagination";
import PixModal from "../components/PixModal";
import {
  APPOINTMENT_STATUS_META,
  brl,
  type Appointment,
  CHANGE_CUTOFF_MINUTES,
  type Barber,
  useAppointments,
  useBarbers,
  useBook,
  useCredits,
  useCancelAppointment,
  useQuota,
  useReschedule,
  usePaymentConfig,
  useSlots,
} from "../features/barbershop/api";
import { addDays, dateStr } from "../lib/dates";

/** Agendamentos por página em "Meus horários". */
const POR_PAGINA = 5;
/** Quantos dias para a frente a faixa de datas oferece. */
const DIAS_A_FRENTE = 21;

function erroDe(err: unknown, padrao: string): string {
  return (
    (err as { response?: { data?: { error?: { message?: string } } } }).response?.data?.error
      ?.message ?? padrao
  );
}

const horaDe = (iso: string) =>
  new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

const diaPorExtenso = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
  });

const quandoDe = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

/** Faixa horizontal de dias — o passo 1 do agendamento. */
function DayStrip({ value, onChange }: { value: string; onChange: (d: string) => void }) {
  const hoje = dateStr(new Date());
  const dias = useMemo(
    () => Array.from({ length: DIAS_A_FRENTE }, (_, i) => addDays(hoje, i)),
    [hoje],
  );

  return (
    <div className="day-strip">
      {dias.map((d) => {
        const data = new Date(`${d}T00:00:00`);
        const ativo = d === value;
        return (
          <button
            key={d}
            type="button"
            className={`day-chip${ativo ? " is-active" : ""}`}
            onClick={() => onChange(d)}
            aria-pressed={ativo}
          >
            <span className="day-chip-weekday">
              {data.toLocaleDateString("pt-BR", { weekday: "short" }).replace(".", "")}
            </span>
            <span className="day-chip-number">{data.getDate()}</span>
            <span className="day-chip-month">
              {data.toLocaleDateString("pt-BR", { month: "short" }).replace(".", "")}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function BarberCard({
  barber,
  selected,
  onSelect,
}: {
  barber: Barber;
  selected: boolean;
  onSelect: () => void;
}) {
  const iniciais = barber.display_name
    .split(/\s+/)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <button
      type="button"
      className={`barber-card${selected ? " is-active" : ""}`}
      onClick={onSelect}
      aria-pressed={selected}
    >
      {barber.photo_data ? (
        <img className="barber-avatar" src={barber.photo_data} alt="" />
      ) : (
        <span className="barber-avatar barber-avatar-initials">{iniciais}</span>
      )}
      <span className="barber-card-body">
        <span className="barber-card-name">{barber.display_name}</span>
        <span className="barber-card-meta">
          {barber.schedules.length} {barber.schedules.length === 1 ? "período" : "períodos"} na
          semana
        </span>
      </span>
      {selected && <IconCheck size={18} className="text-primary" />}
    </button>
  );
}

/** Passo 4: escolher o horário e confirmar. Serve para marcar e para remarcar. */
function SlotGrid({
  barberId,
  date,
  onPick,
  picking,
}: {
  barberId: string | null;
  date: string;
  onPick: (startAt: string) => void;
  picking: string | null;
}) {
  const { data: slots, isLoading } = useSlots(barberId, barberId ? date : null);

  if (!barberId) return null;
  if (isLoading) return <div className="text-secondary">Buscando horários…</div>;
  if (!slots?.length) {
    return (
      <div className="empty-inline">
        Nenhum horário livre em {diaPorExtenso(date)}. Tente outro dia.
      </div>
    );
  }
  return (
    <div className="slot-grid">
      {slots.map((s) => (
        <button
          key={s.start_at}
          type="button"
          className="slot-chip"
          disabled={picking !== null}
          onClick={() => onPick(s.start_at)}
        >
          {picking === s.start_at ? "…" : horaDe(s.start_at)}
        </button>
      ))}
    </div>
  );
}

function RescheduleModal({
  appointment,
  onClose,
}: {
  appointment: Appointment;
  onClose: () => void;
}) {
  const [dia, setDia] = useState(dateStr(new Date(appointment.start_at)));
  const [erro, setErro] = useState<string | null>(null);
  const [movendo, setMovendo] = useState<string | null>(null);
  const reschedule = useReschedule();

  async function mover(startAt: string) {
    setErro(null);
    setMovendo(startAt);
    try {
      await reschedule.mutateAsync({ id: appointment.id, start_at: startAt });
      onClose();
    } catch (err) {
      setErro(erroDe(err, "Não foi possível remarcar."));
    } finally {
      setMovendo(null);
    }
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Remarcar com {appointment.barber_name}</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <div className="modal-body">
              <div className="text-secondary mb-2">
                Hoje marcado para {quandoDe(appointment.start_at)}.
              </div>
              {erro && <div className="alert alert-danger py-2">{erro}</div>}
              <DayStrip value={dia} onChange={setDia} />
              <div className="mt-3">
                <SlotGrid
                  barberId={appointment.barber}
                  date={dia}
                  onPick={mover}
                  picking={movendo}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-link" onClick={onClose}>
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

export default function BarbershopPage() {
  const [dia, setDia] = useState(dateStr(new Date()));
  const [barbeiro, setBarbeiro] = useState<string | null>(null);
  const [assinante, setAssinante] = useState<boolean | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [marcando, setMarcando] = useState<string | null>(null);
  const [pagina, setPagina] = useState(1);
  const [erroMarcacao, setErroMarcacao] = useState<string | null>(null);
  const [remarcando, setRemarcando] = useState<Appointment | null>(null);
  const [pagando, setPagando] = useState<Appointment | null>(null);

  const barbers = useBarbers({ date: dia, onlyActive: true });
  const quota = useQuota(dia);
  const cobranca = usePaymentConfig();
  const credito = useCredits();
  const book = useBook();
  const cancel = useCancelAppointment();
  const meus = useAppointments({ scope: "mine", page: pagina, pageSize: POR_PAGINA });

  // Trocar de dia pode tirar o barbeiro escolhido da lista — recomeça o passo 2.
  useEffect(() => {
    if (barbeiro && barbers.data && !barbers.data.some((b) => b.id === barbeiro)) {
      setBarbeiro(null);
    }
  }, [barbeiro, barbers.data]);

  // Mudou dia, barbeiro ou tipo: o erro anterior não descreve mais a escolha.
  useEffect(() => {
    setErroMarcacao(null);
  }, [dia, barbeiro, assinante]);

  // O alerta empurra a grade para baixo e pode nascer fora da tela; sem isto a
  // pessoa clica no horário e tem a impressão de que nada aconteceu.
  const alertaRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (erroMarcacao) alertaRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [erroMarcacao]);

  const semCota = assinante === true && quota.data?.remaining === 0;
  // Crédito que cobre o corte inteiro dispensa o Pix (RN-BB9).
  const saldo = Number(credito.data?.balance ?? 0);
  const cobreComCredito = saldo >= Number(cobranca.data?.walk_in_price ?? Infinity);

  async function marcar(startAt: string) {
    if (!barbeiro || assinante === null) return;
    setErroMarcacao(null);
    setAviso(null);
    setMarcando(startAt);
    try {
      const feito = await book.mutateAsync({
        barber: barbeiro,
        start_at: startAt,
        is_subscriber: assinante,
      });
      setPagina(1);
      if (feito.status === "awaiting_payment") {
        setPagando(feito);
      } else if (feito.paid_with_credit) {
        setAviso(
          `Pronto! ${quandoDe(feito.start_at)} com ${feito.barber_name}, pago com seu crédito.`,
        );
      } else {
        setAviso(`Pronto! ${quandoDe(feito.start_at)} com ${feito.barber_name}.`);
      }
    } catch (err) {
      // Fica ao lado dos horários, não no topo: é onde a pessoa acabou de clicar.
      setErroMarcacao(erroDe(err, "Não foi possível marcar esse horário."));
    } finally {
      setMarcando(null);
    }
  }

  async function cancelar(a: Appointment) {
    const jaPago = a.paid_with_credit || a.payment?.status === "approved";
    const pergunta = jaPago
      ? `Cancelar o horário de ${quandoDe(a.start_at)}? O valor de R$ ${brl(a.price)} volta como crédito no seu perfil.`
      : `Cancelar o horário de ${quandoDe(a.start_at)}?`;
    if (!confirm(pergunta)) return;
    setErro(null);
    try {
      await cancel.mutateAsync(a.id);
    } catch (err) {
      setErro(erroDe(err, "Não foi possível cancelar."));
    }
  }

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <div className="page-pretitle">Serviço de barbearia</div>
            <h2 className="page-title">Marcar horário</h2>
          </div>
        </div>
      </div>

      {erro && (
        <div className="alert alert-danger mt-3 d-flex align-items-center">
          <span className="flex-fill">{erro}</span>
          <button className="btn btn-sm btn-ghost-secondary" onClick={() => setErro(null)}>
            Fechar
          </button>
        </div>
      )}
      {aviso && (
        <div className="alert alert-success mt-3 d-flex align-items-center">
          <IconCheck size={18} className="me-2" />
          <span className="flex-fill">{aviso}</span>
          <button className="btn btn-sm btn-ghost-secondary" onClick={() => setAviso(null)}>
            Fechar
          </button>
        </div>
      )}

      {/* Passo 1 — o dia */}
      <section className="card mt-3">
        <div className="card-body">
          <div className="step-head">
            <span className="step-number">1</span>
            <div>
              <div className="step-title">Escolha o dia</div>
              <div className="step-hint">{diaPorExtenso(dia)}</div>
            </div>
            <input
              type="date"
              className="form-control w-auto ms-auto"
              value={dia}
              min={dateStr(new Date())}
              onChange={(e) => e.target.value && setDia(e.target.value)}
            />
          </div>
          <DayStrip value={dia} onChange={setDia} />
        </div>
      </section>

      {/* Passo 2 — o barbeiro */}
      <section className="card mt-3">
        <div className="card-body">
          <div className="step-head">
            <span className="step-number">2</span>
            <div>
              <div className="step-title">Escolha o barbeiro</div>
              <div className="step-hint">Só aparece quem atende nesse dia.</div>
            </div>
          </div>
          {barbers.isLoading && <div className="text-secondary">Carregando…</div>}
          {!barbers.isLoading && !barbers.data?.length && (
            <div className="empty-inline">
              <IconScissors size={18} className="me-2" />
              Nenhum barbeiro atende em {diaPorExtenso(dia)}.
            </div>
          )}
          <div className="barber-list">
            {barbers.data?.map((b) => (
              <BarberCard
                key={b.id}
                barber={b}
                selected={barbeiro === b.id}
                onSelect={() => setBarbeiro(b.id)}
              />
            ))}
          </div>
        </div>
      </section>

      {/* Passo 3 — assinante ou avulso */}
      {barbeiro && (
        <section className="card mt-3">
          <div className="card-body">
            <div className="step-head">
              <span className="step-number">3</span>
              <div>
                <div className="step-title">Você é assinante?</div>
                <div className="step-hint">
                  Assinante tem {quota.data?.limit ?? 3} cortes por mês.
                </div>
              </div>
            </div>
            <div className="plan-choice">
              <button
                type="button"
                className={`plan-card${assinante === true ? " is-active" : ""}`}
                onClick={() => setAssinante(true)}
                aria-pressed={assinante === true}
              >
                <IconTicket size={22} />
                <span className="plan-name">Sou assinante</span>
                <span className="plan-detail">
                  {quota.data
                    ? `${quota.data.remaining} de ${quota.data.limit} cortes neste mês`
                    : "Carregando cota…"}
                </span>
              </button>
              <button
                type="button"
                className={`plan-card${assinante === false ? " is-active" : ""}`}
                onClick={() => setAssinante(false)}
                aria-pressed={assinante === false}
                disabled={cobranca.data?.pix_enabled === false && !cobreComCredito}
              >
                <IconCurrencyReal size={22} />
                <span className="plan-name">Corte avulso</span>
                <span className="plan-detail">
                  {cobranca.data?.pix_enabled === false && !cobreComCredito
                    ? "Indisponível: o Pix ainda não foi configurado nesta instalação."
                    : cobreComCredito
                      ? `Você tem R$ ${brl(saldo)} de crédito — este corte sai sem pagar nada`
                      : cobranca.data
                        ? `R$ ${brl(cobranca.data.walk_in_price)} por Pix — o horário só é confirmado depois do pagamento`
                        : "Pagamento por Pix"}
                </span>
              </button>
            </div>
            {semCota && (
              <div className="alert alert-warning mt-3 mb-0">
                Você já usou os {quota.data?.limit} cortes de assinante deste mês. Dá para marcar
                como avulso ou escolher um dia do mês que vem.
              </div>
            )}
          </div>
        </section>
      )}

      {/* Passo 4 — o horário */}
      {barbeiro && assinante !== null && !semCota && (
        <section className="card mt-3">
          <div className="card-body">
            <div className="step-head">
              <span className="step-number">4</span>
              <div>
                <div className="step-title">Escolha o horário</div>
                <div className="step-hint">Clique no horário para confirmar.</div>
              </div>
            </div>
            {erroMarcacao && (
              <div ref={alertaRef} className="alert alert-danger d-flex align-items-center">
                <span className="flex-fill">{erroMarcacao}</span>
                <button
                  className="btn btn-sm btn-ghost-secondary"
                  onClick={() => setErroMarcacao(null)}
                >
                  Fechar
                </button>
              </div>
            )}
            <SlotGrid barberId={barbeiro} date={dia} onPick={marcar} picking={marcando} />
          </div>
        </section>
      )}

      {/* Meus horários */}
      <div className="mt-4 mb-2 d-flex align-items-baseline flex-wrap gap-2">
        <h3 className="m-0 d-flex align-items-center gap-2">
          <IconCalendarEvent size={20} />
          Meus horários
        </h3>
        <span className="text-secondary small">
          Remarcar e cancelar valem até {CHANGE_CUTOFF_MINUTES} minutos antes da hora marcada.
        </span>
      </div>
      <div className="card">
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th>Quando</th>
                <th>Barbeiro</th>
                <th>Tipo</th>
                <th>Situação</th>
                <th className="w-1" />
              </tr>
            </thead>
            <tbody>
              {meus.isLoading && (
                <tr>
                  <td colSpan={5} className="text-secondary">
                    Carregando…
                  </td>
                </tr>
              )}
              {!meus.isLoading && meus.data?.count === 0 && (
                <tr>
                  <td colSpan={5} className="text-secondary">
                    Você ainda não marcou nenhum horário.
                  </td>
                </tr>
              )}
              {meus.data?.results.map((a) => {
                const meta = APPOINTMENT_STATUS_META[a.status];
                return (
                  <tr key={a.id}>
                    <td className="text-nowrap">{quandoDe(a.start_at)}</td>
                    <td>{a.barber_name}</td>
                    <td>
                      {a.is_subscriber ? (
                        <span className="badge bg-purple-lt">Assinante</span>
                      ) : a.paid_with_credit ? (
                        <span className="badge bg-teal-lt">Crédito</span>
                      ) : (
                        <span className="badge bg-secondary-lt">R$ {brl(a.price)}</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${meta.cls}`}>{meta.label}</span>
                    </td>
                    <td>
                      {a.can_change ? (
                        <div className="btn-list flex-nowrap justify-content-end">
                          {a.status === "awaiting_payment" ? (
                            <button
                              className="btn btn-sm btn-primary"
                              onClick={() => setPagando(a)}
                            >
                              Pagar
                            </button>
                          ) : (
                            <button
                              className="btn btn-sm btn-outline-primary"
                              onClick={() => setRemarcando(a)}
                            >
                              Remarcar
                            </button>
                          )}
                          <button
                            className="btn btn-sm btn-icon btn-ghost-danger"
                            title="Cancelar"
                            disabled={cancel.isPending}
                            onClick={() => void cancelar(a)}
                          >
                            <IconX size={16} />
                          </button>
                        </div>
                      ) : (
                        a.status === "scheduled" && (
                          <span className="text-secondary small text-nowrap">
                            Prazo encerrado
                          </span>
                        )
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {(meus.data?.count ?? 0) > POR_PAGINA && (
          <Pagination
            page={pagina}
            count={meus.data?.count ?? 0}
            label={{ one: "horário", many: "horários" }}
            pageSize={POR_PAGINA}
            loading={meus.isFetching}
            onChange={setPagina}
          />
        )}
      </div>

      {remarcando && (
        <RescheduleModal appointment={remarcando} onClose={() => setRemarcando(null)} />
      )}
      {pagando && (
        <PixModal
          appointment={pagando}
          onClose={() => setPagando(null)}
          onPaid={(a) => {
            setAviso(`Pagamento confirmado! ${quandoDe(a.start_at)} com ${a.barber_name}.`);
          }}
        />
      )}
    </>
  );
}
