# Módulo: Inventário 🟡

## Objetivo
Levantamentos periódicos para conferir se os bens cadastrados continuam nos locais indicados, registrando divergências.

## Base legal
**Art. 30, b)** — realizar levantamentos periódicos para conferir se todos os itens cadastrados continuam nos locais indicados.

## Entidades
`Inventory`, `InventoryItem`, `Discrepancy`, `Asset`, `Location`. Ver `dominio/entidades.md`.

## Casos de uso
- **UC-I1 Abrir inventário**: define escopo (local/categoria/todos) e período → sistema gera lista esperada de bens.
- **UC-I2 Conferir em campo (PWA offline)**: inventariante escaneia QR; sistema marca `found`, compara `expected_location_id` × `found_location_id`.
- **UC-I3 Registrar divergência**: não_encontrado / local_divergente / estado_divergente / não_cadastrado.
- **UC-I4 Fechar inventário**: consolida, gera relatório de conformidade + AuditLog. Divergências viram ações (atualizar local, apurar extravio, cadastrar bem).

Fluxo completo em `dominio/fluxos.md#3`.

## Regras (invariantes)
- Inventário fechado é imutável (histórico).
- Atualização de local a partir de divergência exige aprovação do Diretor.
- Contagem offline sincroniza sem perder dados (idempotência por `asset_id`+`inventory_id`).

## Endpoints (contrato)
`POST /api/inventories` · `GET /api/inventories/{id}` · `POST /api/inventories/{id}/scan` · `POST /api/inventories/{id}/close` · `GET /api/inventories/{id}/discrepancies`.

## Permissões
Abrir/fechar: Admin, Diretor. Conferir em campo: Inventariante, Diretor. Ver relatório: Auditor.

## A detalhar (TODO)
- [ ] Estratégia de sync offline (fila local + resolução de conflito).
- [ ] Amostragem vs. inventário total.
