# Regras de Negócio (Invariantes) 🟡

Fonte da verdade das regras que o **Service** deve garantir. Cada regra deve ter teste.

## Multi-tenant
- **RN-T1** Toda leitura/escrita filtra por `tenant_id`. Nenhum recurso cruza tenants.

## Bem (Asset)
- **RN-A1** `asset_tag` único por tenant e imutável após emissão.
- **RN-A2** Transições de `status` seguem a máquina de estados (`dominio/fluxos.md#1`). Transição inválida = erro 422.
- **RN-A3** Bem `baixado` é terminal; não reativa.
- **RN-A4** Exclusão é soft delete; bem com histórico nunca é apagado fisicamente.

## Agenda / Reserva
- **RN-B1** Não pode haver **sobreposição** de reservas aprovadas para o mesmo bem (409).
- **RN-B2** Reserva só em janela de `Availability` do bem.
- **RN-B3** Bem em `manutenção`/`baixado` não é reservável.

## Cautela (Art.30 d)
- **RN-C1** Cautela ativa exige **duas assinaturas** (holder + issuer).
- **RN-C2** Máx. **uma** cautela `ativa` por bem.
- **RN-C3** `condition_out` obrigatório na emissão; `condition_in` na devolução.
- **RN-C4** `due_at < now` + `ativa` → `atrasada` (job) + notificação.
- **RN-C5** Inspeção com dano → abre manutenção; faltante → registra extravio.

## Inventário (Art.30 b)
- **RN-I1** Inventário fechado é imutável.
- **RN-I2** Sync offline idempotente por (`inventory_id`,`asset_id`).
- **RN-I3** Correção de local via divergência exige aprovação do Diretor.

## Auditoria
- **RN-X1** Toda ação sensível grava `AuditLog` (append-only, imutável).

## Convenção
Ao implementar uma regra, referencie o código (`RN-C1`) no teste e no comentário do Service.
