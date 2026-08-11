/**
 * Módulos do sistema. Cada tela pertence a um, e o menu lateral mostra só as
 * telas do módulo em que a pessoa está — trocar de módulo troca o menu.
 */
export type ModuleId = "patrimonio" | "barbearia" | "autenticacao" | "financeiro";

export interface SystemModule {
  id: ModuleId;
  name: string;
  summary: string;
  to: string;
  available: boolean;
  /** Perfis que enxergam o módulo. Ausente = todo mundo que está logado. */
  roles?: string[];
}

export const MODULES: SystemModule[] = [
  {
    id: "patrimonio",
    name: "Sistema de Administração de Patrimônio",
    summary: "Bens, catálogo, agenda de reservas, cautelas e inventário.",
    to: "/",
    available: true,
  },
  {
    id: "barbearia",
    name: "Serviço de Barbearia",
    summary: "Escolha o dia, o barbeiro e o horário. Assinante ou avulso.",
    to: "/barbearia",
    available: true,
  },
  {
    id: "autenticacao",
    name: "Sistema de Autenticação",
    summary: "Cadastro de usuários, perfis de acesso e senhas.",
    to: "/usuarios",
    available: true,
    roles: ["admin"],
  },
  {
    id: "financeiro",
    name: "Sistema Financeiro",
    summary: "Mensalidades, caixa e prestação de contas do grêmio.",
    to: "/financeiro",
    available: false,
    roles: ["admin", "director", "inventory", "auditor"],
  },
];

/** Rotas que pertencem a cada módulo (o resto cai no patrimônio). */
const ROUTES: Record<ModuleId, string[]> = {
  barbearia: ["/barbearia"],
  autenticacao: ["/usuarios"],
  financeiro: ["/financeiro"],
  patrimonio: [],
};

export function moduleForPath(pathname: string): ModuleId {
  for (const [id, rotas] of Object.entries(ROUTES) as [ModuleId, string[]][]) {
    if (rotas.some((r) => pathname === r || pathname.startsWith(`${r}/`))) return id;
  }
  return "patrimonio";
}
