import { IconUsers } from "@tabler/icons-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useAcceptAssociadoInvite } from "../features/finance/api";

export default function AssociadoInvitePage() {
  const { token = "" } = useParams();
  const accept = useAcceptAssociadoInvite();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  async function confirmar() {
    setError(null);
    try {
      await accept.mutateAsync(token);
      navigate("/perfil", { replace: true });
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response
        ?.data?.error?.message;
      setError(msg ?? "Não foi possível aceitar o convite.");
    }
  }

  return (
    <div className="page page-center">
      <div className="container container-tight py-4">
        <div className="card card-md">
          <div className="card-body text-center py-5">
            <IconUsers size={40} className="mb-3 text-primary" />
            <h2 className="mb-2">Convite para o Associado</h2>
            <p className="text-secondary mb-4">
              R$ 30,00 por mês, com direito a 4 cortes na barbearia. Confirmar
              ativa a cobrança a partir de hoje.
            </p>
            {error && <div className="alert alert-danger">{error}</div>}
            <button className="btn btn-primary w-100" onClick={confirmar} disabled={accept.isPending}>
              {accept.isPending ? "Confirmando…" : "Aceitar e virar Associado"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
