import { IconCheck, IconClock, IconCopy } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { brl } from "../features/barbershop/api";
import {
  useFinancePixStatus,
  useInitiatePixPayment,
  type MyFinanceSummary,
} from "../features/finance/api";

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

/**
 * Pagamento da mensalidade por Pix. Confirmação é sempre do provedor —
 * nunca do clique do usuário (RN-P2), mesmo padrão do PixModal da Barbearia,
 * só que aqui a cobrança é da mensalidade, não de um agendamento.
 */
export default function FinancePixModal({
  resumo,
  onClose,
}: {
  resumo: MyFinanceSummary;
  onClose: () => void;
}) {
  const [fase, setFase] = useState<"valor" | "pix">("valor");
  const [valor, setValor] = useState(resumo.pending_amount || "0.00");
  const [pixId, setPixId] = useState<string | null>(null);
  const [copiado, setCopiado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const qc = useQueryClient();
  const iniciar = useInitiatePixPayment();
  const status = useFinancePixStatus(pixId, fase === "pix");
  const pagamento = status.data ?? iniciar.data ?? null;
  const restam = useCountdown(pagamento?.expires_at);

  const pago = pagamento?.status === "approved";
  const perdido = pagamento != null && ["expired", "rejected", "cancelled"].includes(pagamento.status);

  // Invalidar fora do queryFn, de propósito: `useFinancePixStatus` também
  // começa com "finance" na chave, então invalidar de dentro do próprio
  // fetch reentra nele mesmo e o resultado nunca assenta (achado ao vivo —
  // a barbearia já resolve assim no PixModal, reagindo ao estado derivado).
  useEffect(() => {
    if (!pago && !perdido) return;
    qc.invalidateQueries({ queryKey: ["finance"] });
  }, [pago, perdido, qc]);

  const porMes =
    resumo.months_open > 0 ? Number(resumo.pending_amount) / resumo.months_open : null;
  const meses = porMes && Number(valor) > 0 ? Math.floor(Number(valor) / porMes) : 0;

  async function gerarPix(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    try {
      const payment = await iniciar.mutateAsync(valor);
      setPixId(payment.id);
      setFase("pix");
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response
        ?.data?.error?.message;
      setErro(msg ?? "Não foi possível gerar o Pix.");
    }
  }

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
                {fase === "valor"
                  ? "Pagar mensalidade"
                  : pago
                    ? "Pagamento confirmado"
                    : perdido
                      ? "Pagamento não concluído"
                      : "Pague com Pix"}
              </h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>

            {fase === "valor" && (
              <form onSubmit={gerarPix}>
                <div className="modal-body">
                  {erro && <div className="alert alert-danger">{erro}</div>}
                  <label className="form-label required">Valor</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    className="form-control"
                    value={valor}
                    onChange={(e) => setValor(e.target.value)}
                    required
                  />
                  {meses > 0 && (
                    <div className="alert alert-info mt-3 mb-0">
                      Esse valor cobre {meses} {meses === 1 ? "mês" : "meses"} de mensalidade.
                    </div>
                  )}
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-link" onClick={onClose}>
                    Cancelar
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={iniciar.isPending}>
                    {iniciar.isPending ? "Gerando…" : "Gerar Pix"}
                  </button>
                </div>
              </form>
            )}

            {fase === "pix" && (
              <>
                <div className="modal-body text-center">
                  {pago && (
                    <>
                      <div className="pix-done">
                        <IconCheck size={36} />
                      </div>
                      <p className="mb-0">Pagamento confirmado. Sua mensalidade foi atualizada.</p>
                    </>
                  )}

                  {perdido && (
                    <p className="mb-0 text-secondary">
                      O prazo do Pix acabou. Feche esta tela e gere um novo quando quiser.
                    </p>
                  )}

                  {!pago && !perdido && pagamento && (
                    <>
                      <div className="pix-amount">R$ {brl(pagamento.amount)}</div>
                      {pagamento.qr_code_base64 && (
                        <img
                          className="pix-qr"
                          src={`data:image/png;base64,${pagamento.qr_code_base64}`}
                          alt="QR Code do Pix"
                        />
                      )}
                      <button
                        type="button"
                        className="btn btn-primary w-100 mt-3"
                        onClick={copiar}
                      >
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
                            Vale por <strong>{relogio(restam)}</strong>
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
              </>
            )}
          </div>
        </div>
      </div>
      <div className="modal-backdrop fade show" />
    </>
  );
}
