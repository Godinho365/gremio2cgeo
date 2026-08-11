/** Utilitários de data no fuso local (a agenda trabalha com dias, não horas). */

const pad = (n: number) => String(n).padStart(2, "0");

/** Date → "YYYY-MM-DD" local. */
export const dateStr = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** "YYYY-MM-DD" + n dias → "YYYY-MM-DD". */
export function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return dateStr(d);
}
