export default function PlaceholderPage({ title }: { title: string }) {
  return (
    <>
      <div className="page-header">
        <h2 className="page-title">{title}</h2>
      </div>
      <div className="empty mt-4">
        <p className="empty-title">Em breve</p>
        <p className="empty-subtitle text-secondary">
          O módulo {title} será implementado em um próximo sprint.
        </p>
      </div>
    </>
  );
}
