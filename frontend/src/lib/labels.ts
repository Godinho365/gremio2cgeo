import { ORG_NAME } from "../branding";

export interface LabelItem {
  asset_tag: string;
  name: string;
  qrUrl: string; // data URL do QR (ver fetchAssetQrUrl)
}

/** Máximo de etiquetas por folha A4 (grade 4×4). */
export const LABELS_PER_SHEET = 16;

const esc = (s: string) =>
  s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

function chunk<T>(items: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

/**
 * Abre a janela de impressão com as etiquetas em folha A4 — até 16 por folha,
 * quebrando em folhas novas quando passa disso.
 */
export function printLabelSheet(items: LabelItem[]): boolean {
  if (items.length === 0) return true;
  const win = window.open("", "_blank", "width=900,height=700");
  if (!win) return false; // pop-up bloqueado

  const sheets = chunk(items, LABELS_PER_SHEET)
    .map(
      (sheet, i, all) => `
        <div class="sheet${i < all.length - 1 ? " break" : ""}">
          ${sheet
            .map(
              (it) => `
            <div class="label">
              <div class="org">${esc(ORG_NAME)}</div>
              <img src="${it.qrUrl}" alt="QR ${esc(it.asset_tag)}" />
              <div class="tag">${esc(it.asset_tag)}</div>
              <div class="name">${esc(it.name)}</div>
            </div>`,
            )
            .join("")}
        </div>`,
    )
    .join("");

  win.document.write(`<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
    <title>Etiquetas patrimoniais</title>
    <style>
      @page { size: A4; margin: 8mm; }
      body { font-family: system-ui, Arial, sans-serif; margin: 0; }
      .sheet {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        grid-auto-rows: min-content;
        gap: 4mm;
      }
      .sheet.break { page-break-after: always; }
      .label {
        border: 1.5px solid #111;
        border-radius: 8px;
        padding: 6px 4px;
        text-align: center;
        break-inside: avoid;
        page-break-inside: avoid;
      }
      .label img { width: 100%; max-width: 32mm; aspect-ratio: 1 / 1; display: block; margin: 0 auto; }
      .org { font-size: 7px; letter-spacing: .5px; text-transform: uppercase; color: #666; margin-bottom: 3px; }
      .tag { font-size: 12px; font-weight: 800; letter-spacing: .5px; margin-top: 4px; }
      .name { font-size: 9px; color: #444; line-height: 1.2; overflow: hidden; }
      @media screen { body { background: #f1f5f9; padding: 8mm; } .sheet { background: #fff; padding: 8mm; margin-bottom: 8mm; } }
    </style></head>
    <body>${sheets}
    <script>window.onload=function(){window.focus();window.print();};</script>
    </body></html>`);
  win.document.close();
  return true;
}
