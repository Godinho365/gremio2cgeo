import { IconChevronLeft, IconChevronRight, IconUserOff, IconX } from "@tabler/icons-react";
import { useState } from "react";

import {
  APPOINTMENT_STATUS_META,
  brl,
  type Appointment,
  useAppointments,
  useBarbers,
  useCancelAppointment,
  useFinishAppointment,
} from "../features/barbershop/api";
import { addDays, dateStr } from "../lib/dates";

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
    year: "numeric",
  });

function Stat({ label, value, cls }: { label: string; value: number | string; cls?: string }) {
  return (
    <div className="col">
      <div className="card card-sm">
        <div className="card-body text-center">
          <div className={`h1 m-0 ${cls ?? ""}`}>{value}</div>
          <div className="text-secondary">{label}</div>
        </div>
      </div>
    </div>
  );
}

export default function BarbershopAgendaPage() {
  const [dia, setDia] = useState(dateStr(new Date()));
  const [barbeiro, setBarbeiro] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  const barbers = useBarbers();
  const finish = useFinishAppointment();
  const cancel = useCancelAppointment();
  const { data, isLoading } = useAppointments({
    scope: "all",
    date: dia,
    barber: barbeiro || undefined,
    pageSize: 100,
  });

  const doDia = (data?.results ?? [])
    .slice()
    .sort((a, b) => a.start_at.localeCompare(b.start_at));
  const agendados = doDia.filter((a) => a.status === "scheduled");
  const emAtendimento = doDia.filter((a) => a.status === "active");
  const finalizados = doDia.filter((a) => a.status === "completed");
  const aReceber = doDia
    .filter((a) => !a.is_subscriber && a.status !== "cancelled")
    .reduce((total, a) => total + Number(a.price), 0);

  async function agir(fn: () => Promise<unknown>, padrao: string) {
    setErro(null);
    try {
      await fn();
    } catch (err) {
      setErro(erroDe(err, padrao));
    }
  }

  async function encerrar(a: Appointment, noShow: boolean) {
    await agir(
      () => finish.mutateAsync({ id: a.id, noShow }),
      "Não foi possível encerrar o atendimento.",
    );
  }

  async function cancelar(a: Appointment) {
    if (!confirm(`Cancelar o horário de ${a.customer_name} às ${horaDe(a.start_at)}?`)) return;
    await agir(() => cancel.mutateAsync(a.id), "Não foi possível cancelar.");
  }

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <div className="page-pretitle">Serviço de barbearia</div>
            <h2 className="page-title">Agenda do dia</h2>
          </div>
          <div className="col-auto ms-auto">
            <div className="btn-list flex-nowrap align-items-center">
              <button
                className="btn btn-icon btn-ghost-secondary"
                title="Dia anterior"
                onClick={() => setDia((d) => addDays(d, -1))}
              >
                <IconChevronLeft size={18} />
              </button>
              <input
                type="date"
                className="form-control w-auto"
                value={dia}
                onChange={(e) => e.target.value && setDia(e.target.value)}
              />
              <button
                className="btn btn-icon btn-ghost-secondary"
                title="Próximo dia"
                onClick={() => setDia((d) => addDays(d, 1))}
              >
                <IconChevronRight size={18} />
              </button>
              <button className="btn btn-outline-primary" onClick={() => setDia(dateStr(new Date()))}>
                Hoje
              </button>
            </div>
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

      <div className="row row-cards mt-1 mb-3">
        <Stat label="Marcados" value={agendados.length} cls="text-blue" />
        <Stat label="Em atendimento" value={emAtendimento.length} cls="text-azure" />
        <Stat label="Finalizados" value={finalizados.length} cls="text-green" />
        <Stat label="A receber" value={`R$ ${aReceber.toFixed(2).replace(".", ",")}`} />
      </div>

      <div className="card">
        <div className="card-header d-flex align-items-center gap-2 flex-wrap">
          <span className="text-secondary text-capitalize">{diaPorExtenso(dia)}</span>
          <select
            className="form-select w-auto ms-auto"
            value={barbeiro}
            onChange={(e) => setBarbeiro(e.target.value)}
          >
            <option value="">Todos os barbeiros</option>
            {barbers.data?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.display_name}
              </option>
            ))}
          </select>
        </div>
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th className="w-1">Hora</th>
                <th>Cliente</th>
                <th>Barbeiro</th>
                <th>Tipo</th>
                <th>Situação</th>
                <th className="w-1" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={6} className="text-secondary">
                    Carregando…
                  </td>
                </tr>
              )}
              {!isLoading && doDia.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-secondary">
                    Nenhum horário marcado neste dia.
                  </td>
                </tr>
              )}
              {doDia.map((a) => {
                const meta = APPOINTMENT_STATUS_META[a.status];
                return (
                  <tr key={a.id}>
                    <td className="asset-tag text-nowrap">{horaDe(a.start_at)}</td>
                    <td className="fw-medium">{a.customer_name}</td>
                    <td>{a.barber_name}</td>
                    <td>
                      {a.is_subscriber ? (
                        <span className="badge bg-purple-lt">Assinante</span>
                      ) : (
                        <span className="badge bg-secondary-lt">R$ {brl(a.price)}</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${meta.cls}`}>{meta.label}</span>
                    </td>
                    <td>
                      <div className="btn-list flex-nowrap justify-content-end">
                        {a.status === "scheduled" && (
                          <button
                            className="btn btn-sm btn-icon btn-ghost-danger"
                            title="Cancelar"
                            disabled={cancel.isPending}
                            onClick={() => void cancelar(a)}
                          >
                            <IconX size={16} />
                          </button>
                        )}
                        {(a.status === "active" || a.status === "completed") && (
                          <button
                            className="btn btn-sm btn-outline-secondary"
                            disabled={finish.isPending}
                            onClick={() => void encerrar(a, true)}
                          >
                            <IconUserOff size={16} className="me-1" />
                            Não compareceu
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
