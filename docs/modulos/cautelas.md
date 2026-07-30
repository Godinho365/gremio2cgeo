# Módulo: Cautelas ✅

## Objetivo
Controlar a entrega de um bem a um associado sob **termo de responsabilidade assinado**, e a devolução com **inspeção** de estado.

## Base legal
**Estatuto Art. 30, d)** — "emitir e coletar assinaturas nos termos de cautela e responsabilidade sempre que um bem da instituição for entregue para o uso de um associado, bem como realizar inspeção quando da devolução deste."

## Entidades
`Custody`, `Return`, `Inspection`, `Attachment` (termo + assinaturas + fotos), `Asset`, `Booking`. Ver `dominio/entidades.md`.

## Casos de uso

### UC-C1 — Emitir cautela
- **Ator**: Diretor Patrimonial.
- **Pré**: bem `disponível` ou `reservado`; associado (holder) identificado.
- **Passos**: seleciona bem → informa holder e `due_at` → registra `condition_out` (+fotos) → sistema gera PDF do termo → coleta assinatura do holder e do issuer → confirma.
- **Pós**: `Custody.status = ativa`; `Asset.status = em_uso`; AuditLog.
- **Exceções**: bem indisponível → bloqueia; falta uma assinatura → cautela **não** é criada.

### UC-C2 — Devolver bem + inspeção
- **Ator**: Diretor Patrimonial (recebe).
- **Pré**: cautela `ativa` ou `atrasada`.
- **Passos**: abre cautela → registra `Return` (data, recebedor) → faz `Inspection` (`condition_in`, dano?, fotos) → define `outcome`.
- **Pós**:
  - `outcome=ok` → `Custody.status=devolvida`, `Asset.status=disponível`.
  - `outcome=dano` → abre `Maintenance` (Art.30 c), `Asset.status=manutenção`.
  - `outcome=faltante` → registra extravio, notifica, AuditLog.

### UC-C3 — Cautela atrasada
- **Ator**: sistema (job Celery).
- **Regra**: `status=ativa` e `due_at < now` → `status=atrasada` + notifica holder e diretor.

### UC-C4 — Consultar histórico de responsabilidade de um bem/pessoa
- **Ator**: Diretor, Auditor. Lista todas as cautelas por `asset` ou por `holder`.

## Fluxo (sem assinatura)
`solicitada (pending) → aprovada (active) / rejeitada` · `ativa → devolvida` · pode ser `excluída` (soft delete).
A cautela é **solicitada** por qualquer usuário e **aprovada/rejeitada** pelo gestor (Admin/Diretor). Não há assinatura eletrônica no MVP — o controle é pela aprovação + AuditLog (quem aprovou/rejeitou).

## Regras de negócio (invariantes)
1. Emissão cria cautela **solicitada (pending)**; só o gestor **aprova/rejeita/exclui**.
2. `condition_out` obrigatório na solicitação; `condition_in` obrigatório na devolução.
3. Ao **aprovar**: bem deve estar disponível/reservado e ter **no máximo uma** cautela ativa (RN-C2); então vira `em_uso`.
4. `due_at < now` + `ativa` → `atrasada` (job Celery, RN-C4).
5. Inspeção com dano → manutenção; faltante → extraviada (RN-C5).
6. Se veio de `Booking`, a cautela referencia `booking_id` e conclui a reserva na aprovação. Toda transição gera AuditLog.

## Endpoints (contrato)
| Método | Path | Ação |
|---|---|---|
| POST | `/api/custodies` | emitir cautela |
| POST | `/api/custodies/{id}/sign` | registrar assinatura (holder/issuer) |
| GET | `/api/custodies/{id}/term` | baixar PDF do termo |
| POST | `/api/custodies/{id}/return` | registrar devolução + inspeção |
| GET | `/api/custodies?asset=&holder=&status=` | listar/filtrar |

## Permissões por perfil
| Ação | Admin | Diretor Patr. | Inventariante | Usuário | Auditor |
|---|:-:|:-:|:-:|:-:|:-:|
| Emitir/devolver cautela | ✓ | ✓ | – | – | – |
| Assinar como holder | – | – | – | ✓ (própria) | – |
| Ver histórico | ✓ | ✓ | ✓ | ✓ (próprio) | ✓ |

## Estados
`ativa → devolvida` · `ativa → atrasada → devolvida` · `ativa → devolvida(faltante/dano)`.

## Fora de escopo (agora)
Assinatura com certificado digital ICP-Brasil (futuro); por ora assinatura eletrônica simples com trilha de auditoria (timestamp + IP + hash do termo).
