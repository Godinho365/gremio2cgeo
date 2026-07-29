# Módulo: Patrimônio 🟡

## Objetivo
Catalogar bens (compra/doação), com numeração patrimonial e etiqueta QR, e manter seu ciclo de vida.

## Base legal
**Art. 30, a)** — identificar e catalogar bens através de relação e etiquetas com numeração patrimonial.

## Entidades
`Asset`, `AssetLabel`, `Category`, `Location`, `Acquisition`, `Supplier`, `Attachment`. Ver `dominio/entidades.md`.

## Casos de uso
- **UC-P1 Cadastrar bem**: registra Acquisition → cria Asset → gera `asset_tag` (`PAT-{ano}-{seq}` por tenant) → emite etiqueta QR. Ver fluxo em `dominio/fluxos.md#4`.
- **UC-P2 Imprimir/reimprimir etiqueta**: gera QR apontando para `asset_tag`; registra `printed_at`.
- **UC-P3 Mover bem de local**: atualiza `location_id` (com AuditLog).
- **UC-P4 Baixar bem**: `status=baixado`, motivo obrigatório, terminal.

## Regras (invariantes)
- `asset_tag` único por tenant, imutável após emitido.
- Não excluir bem com histórico (soft delete / baixa).
- Toda mudança de local/estado/valor → AuditLog.

## Endpoints (contrato)
`POST /api/assets` · `GET /api/assets?category=&location=&status=` · `GET /api/assets/{id}` · `PATCH /api/assets/{id}` · `POST /api/assets/{id}/label` · `POST /api/assets/{id}/writeoff`.

## Permissões
Cadastro/edição/baixa: Admin, Diretor. Consulta: todos. Mover em campo: Inventariante.

## A detalhar (TODO)
- [ ] Depreciação (`current_value`) — método e periodicidade.
- [ ] Importação em massa (CSV/planilha) para migração inicial.
- [ ] Campos customizáveis por categoria.
