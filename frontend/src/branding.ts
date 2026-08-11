import type { CurrentUser } from "./auth/AuthContext";
import { isStaff } from "./auth/roles";

export const ORG_NAME = "Grêmio do 2º CGEO";
export const SYSTEM_NAME = "Sistema de Administração de Patrimônio";
export const SYSTEM_SHORT_NAME = "SAPA";

export interface BrandText {
  title: string;
  subtitle: string;
}

/**
 * Identidade exibida depois do login: o administrador (e demais perfis de
 * gestão) vê o nome do sistema; o usuário comum vê apenas o grêmio.
 */
export function brandFor(user: CurrentUser | null): BrandText {
  return isStaff(user)
    ? { title: SYSTEM_NAME, subtitle: ORG_NAME }
    : { title: ORG_NAME, subtitle: "" };
}
