import { IconCheck, IconClock, IconCopy } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { type Appointment, brl, usePaymentStatus } from "../features/barbershop/api";

/** Conta regressiva até o Pix vencer, no formato m:ss. */
function useCountdown(deadline: string | null | undefined): number {
  const [restam, setRestam] = useState(() => sobra(deadline));
  useEffect(() => {
    setRestam(sobra(deadline));
    const t = setInterval(() => setRestam(sobra(deadline)), 1000);
    return () => clearInterval(t);
  }, [deadline]);
  return restam;
}

function sobra(deadline: string | null | undefined): number {
  if (!deadline) return 0;
  return Math.max(0, Math.floor((new Date(deadline).getTime() - Date.now()) / 1000));
}

const relogio = (segundos: number) =>
  `${Math.floor(segundos / 60)}:${String(segundos % 60).padStart(2, "0")}`;

const quandoDe = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

/**
 * Pagamento do corte avulso. O horário fica reservado enquanto o Pix vale; se
 * o prazo acabar sem pagamento, o backend libera e a tela avisa.
 */
export default function PixModal({
  appointment,
  onClose,
  onPaid,
}: {
  appointment: Appointment;
  onClose: () => void;
  onPaid: (a: Appointment) => void;
}) {
  const qc = useQueryClient();
  const [copiado, setCopiado] = useState(false);
  // Enquanto está aguardando, pergunta ao backend de 5 em 5 segundos.
  const consulta = usePaymentStatus(appointment.id, appointment.status === "awaiting_payment");
  const atual = consulta.data ?? appointment;
  const pagamento = atual.payment;
  const restam = useCountdown(pagamento?.expires_at);

  const pago = atual.status === "scheduled" || pagamento?.status === "approved";
  const perdido =
    atual.status === "cancelled" ||
    (pagamento != null && ["expired", "rejected", "cancelled"].includes(pagamento.status));

  // Confirmou (ou perdeu o prazo): a lista de horários e os slots livres
  // mudaram de estado no servidor e precisam ser relidos.
  useEffect(() => {
    if (!pago && !perdido) return;
    qc.invalidateQueries({ queryKey: ["appointments"] });
    qc.invalidateQueries({ queryKey: ["slots"] });
    if (pago) onPaid(atual);
  }, [pago, perdido, atual, onPaid, qc]);

  async function copiar() {
    if (!pagamento?.qr_code) return;
    await navigator.clipboard.writeText(pagamento.qr_code);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 2500);
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered modal-sm">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">
                {pago ? "Pagamento confirmado" : perdido ? "Pagamento não concluído" : "Pague com Pix"}
              </h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>

            <div className="modal-body text-center">
              {pago && (
                <>
                  <div className="pix-done">
                    <IconCheck size={36} />
                  </div>
                  <p className="mb-0">
                    Seu horário com <strong>{atual.barber_name}</strong> está garantido para{" "}
                    {quandoDe(atual.start_at)}.
                  </p>
                </>
              )}

              {perdido && (
                <p className="mb-0 text-secondary">
                  O prazo do Pix acabou e o horário voltou para a lista. Marque de novo quando
                  quiser.
                </p>
              )}

              {!pago && !perdido && pagamento && (
                <>
                  <div className="pix-amount">R$ {brl(pagamento.amount)}</div>
                  <div className="text-secondary mb-3">
                    {atual.barber_name} · {quandoDe(atual.start_at)}
                  </div>

                  {pagamento.qr_code_base64 && (
                    <img
                      className="pix-qr"
                      src={`data:image/png;base64,${pagamento.qr_code_base64}`}
                      alt="QR Code do Pix"
                    />
                  )}

                  <button type="button" className="btn btn-primary w-100 mt-3" onClick={copiar}>
                    {copiado ? (
                      <>
                        <IconCheck size={16} className="me-1" />
                        Código copiado
                      </>
                    ) : (
                      <>
                        <IconCopy size={16} className="me-1" />
                        Copiar código Pix
                      </>
                    )}
                  </button>

                  <div className="pix-timer">
                    <IconClock size={16} />
                    {restam > 0 ? (
                      <>
                        O horário fica reservado por <strong>{relogio(restam)}</strong>
                      </>
                    ) : (
                      "Conferindo o pagamento…"
                    )}
                  </div>
                  <p className="text-secondary small mt-2 mb-0">
                    Assim que o pagamento cair, esta tela confirma sozinha.
                  </p>
                </>
              )}
            </div>

            <div className="modal-footer">
              <button type="button" className="btn btn-link w-100" onClick={onClose}>
                {pago || perdido ? "Fechar" : "Pago depois"}
              </button>
            </div>
          </div>
        </div>
      </div>
      <div className="modal-backdrop fade show" />
    </>
  );
}
