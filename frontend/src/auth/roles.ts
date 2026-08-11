import type { CurrentUser } from "./AuthContext";

/** Perfis com acesso aos módulos patrimoniais (o usuário comum só vê perfil e agenda). */
export const STAFF_ROLES = ["admin", "director", "inventory", "auditor"];
export const ADMIN_ROLES = ["admin"];
export const CADASTROS_ROLES = ["admin", "director"];
/** Quem administra a barbearia: barbeiros, grade de trabalho e agenda do dia. */
export const BARBERSHOP_ROLES = ["admin", "barbershop"];
/** Perfis com mais de um módulo — só eles passam pela tela de escolha. */
export const MODULE_CHOOSER_ROLES = [...new Set([...STAFF_ROLES, ...BARBERSHOP_ROLES])];

export function hasAnyRole(user: CurrentUser | null, roles: string[]): boolean {
  const mine = user?.roles ?? [];
  return roles.some((r) => mine.includes(r));
}

export function isStaff(user: CurrentUser | null): boolean {
  return hasAnyRole(user, STAFF_ROLES);
}

export function isAdmin(user: CurrentUser | null): boolean {
  return hasAnyRole(user, ADMIN_ROLES);
}

export function isBarbershopAdmin(user: CurrentUser | null): boolean {
  return hasAnyRole(user, BARBERSHOP_ROLES);
}

/**
 * Quem administra mais de um módulo passa pela tela de escolha. O usuário
 * comum não: ele tem um menu só, com catálogo, agenda e barbearia.
 */
export function canChooseModule(user: CurrentUser | null): boolean {
  return isStaff(user) || isBarbershopAdmin(user);
}

/**
 * Rota inicial após o login: quem administra escolhe o módulo; o usuário comum
 * entra direto no catálogo.
 */
export function homePath(user: CurrentUser | null): string {
  return canChooseModule(user) ? "/modulos" : "/catalogo";
}
