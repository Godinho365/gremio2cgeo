import { IconRefresh } from "@tabler/icons-react";
import { useParams } from "react-router-dom";

import Brand from "../components/Brand";
import { ORG_NAME } from "../branding";
import { usePublicAgenda } from "../features/barbershop/api";

const horaDe = (iso: string) =>
  new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

const STATUS_BADGE: Record<string, string> = {
  scheduled: "bg-blue-lt",
  active: "bg-yellow-lt",
  completed: "bg-green-lt",
  no_show: "bg-red-lt",
  awaiting_payment: "bg-secondary-lt",
};

function dataPorExtenso(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
  });
}

/** Agenda do dia sem login — link público que qualquer barbeiro abre pra
 * ver quem vem hoje, sem precisar de conta no sistema. */
export default function PublicAgendaPage() {
  const { token = "" } = useParams();
  const { data, isLoading, isError, refetch, isFetching } = usePublicAgenda(token);

  return (
    <div className="page">
      <div className="container-xl py-4">
        <div className="d-flex align-items-center justify-content-between mb-4">
          <Brand title="Agenda da Barbearia" subtitle={ORG_NAME} size="md" />
          <button
            type="button"
            className="btn btn-icon btn-ghost-secondary"
            title="Atualizar"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            {isFetching ? (
              <span className="spinner-border spinner-border-sm" />
            ) : (
              <IconRefresh size={20} />
            )}
          </button>
        </div>

        {isError && (
          <div className="alert alert-danger">
            Esse link não é válido ou foi revogado. Peça um link novo pra administração da
            barbearia.
          </div>
        )}

        {!isError && (
          <div className="card">
            <div className="card-header">
              <h3 className="card-title text-capitalize m-0">
                {data ? dataPorExtenso(data.date) : "Carregando…"}
              </h3>
            </div>
            <div className="table-responsive">
              <table className="table table-vcenter card-table">
                <thead>
                  <tr>
                    <th className="w-1">Hora</th>
                    <th>Cliente</th>
                    <th>Barbeiro</th>
                    <th>Situação</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading && (
                    <tr>
                      <td colSpan={4} className="text-secondary">
                        Carregando…
                      </td>
                    </tr>
                  )}
                  {data && data.appointments.length === 0 && (
                    <tr>
                      <td colSpan={4} className="text-secondary text-center py-4">
                        Nenhum horário marcado hoje.
                      </td>
                    </tr>
                  )}
                  {data?.appointments.map((a, i) => (
                    <tr key={i}>
                      <td className="asset-tag text-nowrap">{horaDe(a.start_at)}</td>
                      <td className="fw-medium">{a.customer_name}</td>
                      <td>{a.barber_name}</td>
                      <td>
                        <span className={`badge ${STATUS_BADGE[a.status] ?? "bg-secondary-lt"}`}>
                          {a.status_label}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <p className="text-secondary text-center small mt-3">
          Atualiza sozinha a cada 30 segundos.
        </p>
      </div>
    </div>
  );
}
