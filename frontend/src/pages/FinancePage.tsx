import { IconArrowLeft, IconBuildingBank } from "@tabler/icons-react";
import { Link } from "react-router-dom";

import { MODULES } from "../modules";

/** Módulo financeiro: existe apenas como destino previsto, sem funcionalidade. */
export default function FinancePage() {
  const financeiro = MODULES.find((m) => m.id === "financeiro");

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <div className="page-pretitle">Módulo</div>
            <h2 className="page-title">{financeiro?.name ?? "Sistema Financeiro"}</h2>
          </div>
        </div>
      </div>

      <div className="card mt-3">
        <div className="card-body d-flex flex-column align-items-start gap-3 py-5">
          <span
            className="avatar avatar-lg"
            style={{ backgroundColor: "var(--color-paper-3)", color: "var(--color-neutral)" }}
          >
            <IconBuildingBank size={26} />
          </span>
          <div>
            <div className="h3 mb-1">Em desenvolvimento</div>
            <p className="text-secondary mb-0" style={{ maxWidth: "58ch" }}>
              {financeiro?.summary} Ainda não há nada implementado aqui — o módulo está
              reservado no menu para quando o escopo for definido.
            </p>
          </div>
          <Link to="/modulos" className="btn btn-outline-secondary">
            <IconArrowLeft size={16} className="me-1" />
            Voltar aos módulos
          </Link>
        </div>
      </div>
    </>
  );
}
