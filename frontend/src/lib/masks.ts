/** Máscaras e validações de campos brasileiros, usadas no cadastro e no perfil. */

export const onlyDigits = (s: string) => s.replace(/\D/g, "");

export function maskCpf(s: string): string {
  return onlyDigits(s)
    .slice(0, 11)
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
}

export function maskPhone(s: string): string {
  const d = onlyDigits(s).slice(0, 11);
  if (d.length <= 10) {
    return d.replace(/(\d{2})(\d)/, "($1) $2").replace(/(\d{4})(\d)/, "$1-$2");
  }
  return d.replace(/(\d{2})(\d)/, "($1) $2").replace(/(\d{5})(\d)/, "$1-$2");
}

export function cpfValid(s: string): boolean {
  const c = onlyDigits(s);
  if (c.length !== 11 || /^(\d)\1{10}$/.test(c)) return false;
  for (const len of [9, 10]) {
    let total = 0;
    for (let i = 0; i < len; i++) total += Number(c[i]) * (len + 1 - i);
    const dv = ((total * 10) % 11) % 10;
    if (dv !== Number(c[len])) return false;
  }
  return true;
}

/** "2026-08-06" ou ISO completo → "06/08/2026". */
export function formatDateBr(value?: string | null): string {
  if (!value) return "—";
  const [y, m, d] = value.slice(0, 10).split("-");
  return d ? `${d}/${m}/${y}` : "—";
}
