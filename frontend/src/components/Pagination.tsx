import { IconChevronLeft, IconChevronRight } from "@tabler/icons-react";

export const PAGE_SIZE = 25; // igual ao backend (DefaultPagination)

/** Rodapé de listagem: quantos itens, em que página e as setas. */
export default function Pagination({
  page,
  count,
  label,
  pageSize = PAGE_SIZE,
  loading = false,
  onChange,
}: {
  page: number;
  count: number;
  /** Nome do item no singular, ex.: "bem" → "1–25 de 40 bens". */
  label: { one: string; many: string };
  /** Itens por página — precisa bater com o que a listagem pediu à API. */
  pageSize?: number;
  loading?: boolean;
  onChange: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(count / pageSize));
  const from = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, count);

  return (
    <div className="card-footer d-flex align-items-center flex-wrap gap-2">
      <p className="m-0 text-secondary">
        {count > 0 ? (
          <>
            Mostrando <strong>{from}</strong>–<strong>{to}</strong> de <strong>{count}</strong>{" "}
            {count === 1 ? label.one : label.many}
          </>
        ) : (
          "Sem registros"
        )}
        {loading && <span className="ms-2 spinner-border spinner-border-sm" />}
      </p>
      <div className="ms-auto d-flex align-items-center gap-2">
        <span className="text-secondary">
          Página {page} de {totalPages}
        </span>
        <button
          className="btn btn-sm btn-outline-secondary"
          disabled={page <= 1}
          onClick={() => onChange(Math.max(1, page - 1))}
          title="Página anterior"
        >
          <IconChevronLeft size={16} />
        </button>
        <button
          className="btn btn-sm btn-outline-secondary"
          disabled={page >= totalPages}
          onClick={() => onChange(Math.min(totalPages, page + 1))}
          title="Próxima página"
        >
          <IconChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
