import {
  IconBeach,
  IconClock,
  IconCopy,
  IconPencil,
  IconPlus,
  IconScissors,
  IconTrash,
  IconX,
} from "@tabler/icons-react";
import { useState } from "react";

import {
  type Barber,
  type ScheduleWindow,
  useAddTimeOff,
  useBarbers,
  useCreateBarber,
  useDeleteBarber,
  useRemoveTimeOff,
  useReplicateSchedule,
  useSetSchedule,
  useUpdateBarber,
  WEEKDAYS,
} from "../features/barbershop/api";
import { dateStr } from "../lib/dates";
import { fileToResizedDataUrl } from "../lib/image";
import { maskPhone } from "../lib/masks";

function erroDe(err: unknown, padrao: string): string {
  return (
    (err as { response?: { data?: { error?: { message?: string } } } }).response?.data?.error
      ?.message ?? padrao
  );
}

/** "09:00:00" → "09:00" (o input type=time não aceita segundos). */
const hhmm = (t: string) => t.slice(0, 5);

const diaBr = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("pt-BR");

function BarberFormModal({
  barber,
  onClose,
}: {
  barber: Barber | null;
  onClose: () => void;
}) {
  const create = useCreateBarber();
  const update = useUpdateBarber();
  const [name, setName] = useState(barber?.name ?? "");
  const [nickname, setNickname] = useState(barber?.nickname ?? "");
  const [phone, setPhone] = useState(barber?.phone ?? "");
  const [photo, setPhoto] = useState(barber?.photo_data ?? "");
  const [isActive, setIsActive] = useState(barber?.is_active ?? true);
  const [erro, setErro] = useState<string | null>(null);

  async function escolherFoto(file: File | undefined) {
    if (!file) return;
    try {
      setPhoto(await fileToResizedDataUrl(file, 320));
    } catch (err) {
      setErro((err as Error).message);
    }
  }

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    const body = { name, nickname, phone, photo_data: photo, is_active: isActive };
    try {
      if (barber) await update.mutateAsync({ id: barber.id, ...body });
      else await create.mutateAsync(body);
      onClose();
    } catch (err) {
      setErro(erroDe(err, "Não foi possível salvar o barbeiro."));
    }
  }

  const salvando = create.isPending || update.isPending;

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">{barber ? "Editar barbeiro" : "Novo barbeiro"}</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={salvar}>
              <div className="modal-body">
                {erro && <div className="alert alert-danger py-2">{erro}</div>}
                <div className="mb-3">
                  <label className="form-label required">Nome</label>
                  <input
                    className="form-control"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    autoFocus
                    required
                  />
                </div>
                <div className="row g-2 mb-3">
                  <div className="col">
                    <label className="form-label">Como aparece na agenda</label>
                    <input
                      className="form-control"
                      placeholder="Ex.: Zé"
                      value={nickname}
                      onChange={(e) => setNickname(e.target.value)}
                    />
                  </div>
                  <div className="col">
                    <label className="form-label">Telefone</label>
                    <input
                      className="form-control"
                      value={phone}
                      onChange={(e) => setPhone(maskPhone(e.target.value))}
                    />
                  </div>
                </div>
                <div className="mb-3">
                  <label className="form-label">Foto</label>
                  <div className="d-flex align-items-center gap-3">
                    {photo && <img className="barber-avatar" src={photo} alt="" />}
                    <input
                      type="file"
                      accept="image/*"
                      className="form-control"
                      onChange={(e) => void escolherFoto(e.target.files?.[0])}
                    />
                    {photo && (
                      <button
                        type="button"
                        className="btn btn-sm btn-ghost-danger"
                        onClick={() => setPhoto("")}
                      >
                        Remover
                      </button>
                    )}
                  </div>
                </div>
                <label className="form-check">
                  <input
                    type="checkbox"
                    className="form-check-input"
                    checked={isActive}
                    onChange={(e) => setIsActive(e.target.checked)}
                  />
                  <span className="form-check-label">
                    Atendendo
                    <small className="d-block text-secondary">
                      Desmarque para tirar da lista de agendamento sem perder o histórico.
                    </small>
                  </span>
                </label>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={salvando}>
                  {salvando ? "Salvando…" : "Salvar"}
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

/** Grade semanal: um período por linha, com a duração do atendimento. */
function ScheduleModal({ barber, onClose }: { barber: Barber; onClose: () => void }) {
  const save = useSetSchedule();
  const [windows, setWindows] = useState<ScheduleWindow[]>(
    barber.schedules.map((s) => ({
      weekday: s.weekday,
      start_time: hhmm(s.start_time),
      end_time: hhmm(s.end_time),
      slot_minutes: s.slot_minutes,
    })),
  );
  const [erro, setErro] = useState<string | null>(null);

  function atualizar(i: number, patch: Partial<ScheduleWindow>) {
    setWindows((ws) => ws.map((w, j) => (i === j ? { ...w, ...patch } : w)));
  }

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    try {
      await save.mutateAsync({ id: barber.id, windows });
      onClose();
    } catch (err) {
      setErro(erroDe(err, "Não foi possível salvar os horários."));
    }
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered modal-lg">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Horários de {barber.display_name}</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={salvar}>
              <div className="modal-body">
                {erro && <div className="alert alert-danger py-2">{erro}</div>}
                {windows.length === 0 && (
                  <div className="empty-inline mb-3">
                    Sem horários. Enquanto estiver assim, ninguém consegue marcar com este
                    barbeiro.
                  </div>
                )}
                {windows.map((w, i) => (
                  <div className="row g-2 align-items-end mb-2" key={i}>
                    <div className="col-4">
                      {i === 0 && <label className="form-label">Dia</label>}
                      <select
                        className="form-select"
                        value={w.weekday}
                        onChange={(e) => atualizar(i, { weekday: Number(e.target.value) })}
                      >
                        {WEEKDAYS.map((d) => (
                          <option key={d.value} value={d.value}>
                            {d.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="col">
                      {i === 0 && <label className="form-label">Das</label>}
                      <input
                        type="time"
                        className="form-control"
                        value={w.start_time}
                        onChange={(e) => atualizar(i, { start_time: e.target.value })}
                        required
                      />
                    </div>
                    <div className="col">
                      {i === 0 && <label className="form-label">Às</label>}
                      <input
                        type="time"
                        className="form-control"
                        value={w.end_time}
                        onChange={(e) => atualizar(i, { end_time: e.target.value })}
                        required
                      />
                    </div>
                    <div className="col-3">
                      {i === 0 && <label className="form-label">Cada corte</label>}
                      <div className="input-group">
                        <input
                          type="number"
                          className="form-control"
                          min={5}
                          max={240}
                          step={5}
                          value={w.slot_minutes}
                          onChange={(e) => atualizar(i, { slot_minutes: Number(e.target.value) })}
                          required
                        />
                        <span className="input-group-text">min</span>
                      </div>
                    </div>
                    <div className="col-auto">
                      <button
                        type="button"
                        className="btn btn-icon btn-ghost-danger"
                        title="Remover período"
                        onClick={() => setWindows((ws) => ws.filter((_, j) => j !== i))}
                      >
                        <IconX size={16} />
                      </button>
                    </div>
                  </div>
                ))}
                <button
                  type="button"
                  className="btn btn-sm btn-outline-primary mt-2"
                  onClick={() =>
                    setWindows((ws) => [
                      ...ws,
                      { weekday: 1, start_time: "09:00", end_time: "12:00", slot_minutes: 30 },
                    ])
                  }
                >
                  <IconPlus size={16} className="me-1" />
                  Adicionar período
                </button>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={save.isPending}>
                  {save.isPending ? "Salvando…" : "Salvar horários"}
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

/** "2026-08-20" a "2026-08-25" → "20/08 a 25/08/2026"; um dia só → "20/08/2026". */
function periodoBr(inicio: string, fim: string): string {
  if (inicio === fim) return diaBr(inicio);
  const i = new Date(`${inicio}T00:00:00`);
  return `${i.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })} a ${diaBr(fim)}`;
}

function TimeOffModal({ barber, onClose }: { barber: Barber; onClose: () => void }) {
  const add = useAddTimeOff();
  const remove = useRemoveTimeOff();
  const hoje = dateStr(new Date());
  const [inicio, setInicio] = useState(hoje);
  const [fim, setFim] = useState("");
  const [reason, setReason] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  // Um dia só: deixe o fim em branco. Se recuar o início, o fim acompanha.
  const fimEfetivo = fim && fim >= inicio ? fim : inicio;
  const dias =
    Math.round(
      (new Date(`${fimEfetivo}T00:00:00`).getTime() - new Date(`${inicio}T00:00:00`).getTime()) /
        86400000,
    ) + 1;

  async function lancar(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    try {
      await add.mutateAsync({
        id: barber.id,
        start_date: inicio,
        end_date: fimEfetivo,
        reason,
      });
      setReason("");
      setFim("");
    } catch (err) {
      setErro(erroDe(err, "Não foi possível lançar a folga."));
    }
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Folgas de {barber.display_name}</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <div className="modal-body">
              {erro && <div className="alert alert-danger py-2">{erro}</div>}
              <form className="mb-3" onSubmit={lancar}>
                <div className="row g-2 align-items-end">
                  <div className="col-auto">
                    <label className="form-label required">Primeiro dia</label>
                    <input
                      type="date"
                      className="form-control"
                      value={inicio}
                      onChange={(e) => setInicio(e.target.value)}
                      required
                    />
                  </div>
                  <div className="col-auto">
                    <label className="form-label">Último dia</label>
                    <input
                      type="date"
                      className="form-control"
                      value={fim}
                      min={inicio}
                      onChange={(e) => setFim(e.target.value)}
                    />
                  </div>
                  <div className="col">
                    <label className="form-label">Motivo</label>
                    <input
                      className="form-control"
                      placeholder="Ex.: férias"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </div>
                  <div className="col-auto">
                    <button className="btn btn-primary" disabled={add.isPending}>
                      Lançar
                    </button>
                  </div>
                </div>
                <small className="form-hint mt-1 d-block">
                  Deixe o último dia em branco para uma folga de um dia só.
                  {dias > 1 && ` Este período cobre ${dias} dias.`}
                </small>
              </form>

              {barber.time_off.length === 0 ? (
                <div className="empty-inline">Nenhuma folga lançada.</div>
              ) : (
                <ul className="list-group">
                  {barber.time_off.map((f) => (
                    <li
                      key={f.id}
                      className="list-group-item d-flex align-items-center gap-2"
                    >
                      <span className="fw-medium">{periodoBr(f.start_date, f.end_date)}</span>
                      {f.days > 1 && (
                        <span className="badge bg-orange-lt">{f.days} dias</span>
                      )}
                      <span className="text-secondary">{f.reason}</span>
                      <button
                        className="btn btn-sm btn-icon btn-ghost-danger ms-auto"
                        title={f.days > 1 ? "Remover o período inteiro" : "Remover folga"}
                        disabled={remove.isPending}
                        onClick={() =>
                          void remove.mutateAsync({ id: barber.id, offId: f.id })
                        }
                      >
                        <IconTrash size={16} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
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

/** Copia a grade deste barbeiro para outros — substitui a grade dos escolhidos. */
function ReplicateModal({
  barber,
  todos,
  onClose,
}: {
  barber: Barber;
  todos: Barber[];
  onClose: () => void;
}) {
  const replicar = useReplicateSchedule();
  const [alvos, setAlvos] = useState<string[]>([]);
  const [erro, setErro] = useState<string | null>(null);

  const candidatos = todos.filter((b) => b.id !== barber.id);

  function alternar(id: string) {
    setAlvos((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]));
  }

  async function aplicar(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    try {
      await replicar.mutateAsync({ id: barber.id, targets: alvos });
      onClose();
    } catch (err) {
      setErro(erroDe(err, "Não foi possível replicar os horários."));
    }
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Replicar horários de {barber.display_name}</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={aplicar}>
              <div className="modal-body">
                {erro && <div className="alert alert-danger py-2">{erro}</div>}

                <div className="mb-3">
                  <div className="form-label">Grade que será copiada</div>
                  <GridSummary barber={barber} />
                </div>

                <div className="form-label">Aplicar em</div>
                {candidatos.length === 0 ? (
                  <div className="empty-inline">Não há outro barbeiro cadastrado.</div>
                ) : (
                  candidatos.map((b) => (
                    <label className="form-check" key={b.id}>
                      <input
                        type="checkbox"
                        className="form-check-input"
                        checked={alvos.includes(b.id)}
                        onChange={() => alternar(b.id)}
                      />
                      <span className="form-check-label">
                        {b.display_name}
                        <small className="d-block text-secondary">
                          {b.schedules.length === 0
                            ? "Sem horários — vai passar a atender igual."
                            : `Tem ${b.schedules.length} ${b.schedules.length === 1 ? "período" : "períodos"} hoje, que serão substituídos.`}
                        </small>
                      </span>
                    </label>
                  ))
                )}

                <div className="alert alert-warning mt-3 mb-0">
                  A grade de quem for marcado é <strong>substituída</strong> pela de{" "}
                  {barber.display_name}. Folgas e horários já marcados não são afetados.
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={replicar.isPending || alvos.length === 0}
                >
                  {replicar.isPending
                    ? "Replicando…"
                    : alvos.length === 0
                      ? "Escolha quem recebe"
                      : `Replicar para ${alvos.length} ${alvos.length === 1 ? "barbeiro" : "barbeiros"}`}
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

/** Resumo da grade semanal em uma linha: "Seg 09:00–12:00 · Qua 14:00–18:00". */
function GridSummary({ barber }: { barber: Barber }) {
  if (barber.schedules.length === 0) {
    return <span className="text-secondary">Sem horários definidos</span>;
  }
  return (
    <span className="grid-summary">
      {barber.schedules.map((s) => (
        <span className="grid-summary-item" key={s.id}>
          <strong>{WEEKDAYS[s.weekday].short}</strong> {hhmm(s.start_time)}–{hhmm(s.end_time)}
          <small className="text-secondary"> · {s.slot_minutes}min</small>
        </span>
      ))}
    </span>
  );
}

export default function BarbersPage() {
  const { data, isLoading } = useBarbers();
  const del = useDeleteBarber();
  const [editando, setEditando] = useState<Barber | null>(null);
  const [novo, setNovo] = useState(false);
  const [grade, setGrade] = useState<Barber | null>(null);
  const [folgas, setFolgas] = useState<Barber | null>(null);
  const [replicando, setReplicando] = useState<Barber | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  async function excluir(b: Barber) {
    if (!confirm(`Excluir ${b.display_name} do cadastro?`)) return;
    setErro(null);
    try {
      await del.mutateAsync(b.id);
    } catch (err) {
      setErro(erroDe(err, "Não foi possível excluir."));
    }
  }

  // As modais leem do cache; reabrir com o dado fresco mantém a lista de folgas certa.
  const atual = (b: Barber) => data?.find((x) => x.id === b.id) ?? b;

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <div className="page-pretitle">Serviço de barbearia</div>
            <h2 className="page-title">Barbeiros</h2>
          </div>
          <div className="col-auto ms-auto">
            <button className="btn btn-primary" onClick={() => setNovo(true)}>
              <IconPlus size={18} className="me-1" />
              Novo barbeiro
            </button>
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

      <div className="card mt-3">
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th>Barbeiro</th>
                <th>Dias e horários</th>
                <th>Folgas</th>
                <th>Situação</th>
                <th className="w-1" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={5} className="text-secondary">
                    Carregando…
                  </td>
                </tr>
              )}
              {!isLoading && data?.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-secondary">
                    <IconScissors size={16} className="me-2" />
                    Nenhum barbeiro cadastrado. Comece por “Novo barbeiro”.
                  </td>
                </tr>
              )}
              {data?.map((b) => (
                <tr key={b.id}>
                  <td>
                    <div className="d-flex align-items-center gap-2">
                      {b.photo_data && <img className="barber-avatar sm" src={b.photo_data} alt="" />}
                      <div>
                        <div className="fw-medium">{b.display_name}</div>
                        {b.phone && <div className="text-secondary small">{b.phone}</div>}
                      </div>
                    </div>
                  </td>
                  <td>
                    <GridSummary barber={b} />
                  </td>
                  <td>
                    {b.time_off.length > 0 ? (
                      <span className="badge bg-orange-lt">{b.time_off.length}</span>
                    ) : (
                      <span className="text-secondary">—</span>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${b.is_active ? "bg-green-lt" : "bg-secondary-lt"}`}>
                      {b.is_active ? "Atendendo" : "Fora da escala"}
                    </span>
                  </td>
                  <td>
                    <div className="btn-list flex-nowrap justify-content-end">
                      <button
                        className="btn btn-sm btn-icon btn-ghost-secondary"
                        title="Horários de trabalho"
                        onClick={() => setGrade(b)}
                      >
                        <IconClock size={16} />
                      </button>
                      <button
                        className="btn btn-sm btn-icon btn-ghost-secondary"
                        title="Replicar estes horários para outro barbeiro"
                        disabled={b.schedules.length === 0}
                        onClick={() => setReplicando(b)}
                      >
                        <IconCopy size={16} />
                      </button>
                      <button
                        className="btn btn-sm btn-icon btn-ghost-secondary"
                        title="Folgas"
                        onClick={() => setFolgas(b)}
                      >
                        <IconBeach size={16} />
                      </button>
                      <button
                        className="btn btn-sm btn-icon btn-ghost-secondary"
                        title="Editar"
                        onClick={() => setEditando(b)}
                      >
                        <IconPencil size={16} />
                      </button>
                      <button
                        className="btn btn-sm btn-icon btn-ghost-danger"
                        title="Excluir"
                        disabled={del.isPending}
                        onClick={() => void excluir(b)}
                      >
                        <IconTrash size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {(novo || editando) && (
        <BarberFormModal
          barber={editando}
          onClose={() => {
            setNovo(false);
            setEditando(null);
          }}
        />
      )}
      {grade && <ScheduleModal barber={atual(grade)} onClose={() => setGrade(null)} />}
      {folgas && <TimeOffModal barber={atual(folgas)} onClose={() => setFolgas(null)} />}
      {replicando && (
        <ReplicateModal
          barber={atual(replicando)}
          todos={data ?? []}
          onClose={() => setReplicando(null)}
        />
      )}
    </>
  );
}
