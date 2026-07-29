// Scaffold shell. Real feature routing arrives with the modules (docs/modulos).
export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-5xl px-4 py-4">
          <h1 className="text-xl font-semibold">Patrimonia</h1>
          <p className="text-sm text-slate-500">ERP Patrimonial SaaS — scaffold</p>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">
        <p className="text-slate-600">
          Fundação pronta. Próximo: Sprint 1 (auth) e Sprint 2 (patrimônio).
        </p>
      </main>
    </div>
  );
}
