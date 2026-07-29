# Architecture Decision Records (ADR) 🟡

Registro leve de decisões técnicas importantes. Uma decisão = um arquivo `NNNN-titulo.md`.

## Template
```markdown
# ADR-NNNN: <título>
- Status: proposto | aceito | substituído por ADR-XXXX
- Data: AAAA-MM-DD

## Contexto
Qual problema/força motiva a decisão.

## Decisão
O que foi decidido.

## Consequências
Trade-offs, o que ganhamos e o que abrimos mão.
```

## Índice
| ADR | Título | Status |
|---|---|---|
| 0001 | Multi-tenant: shared schema com `tenant_id` | aceito (ver `arquitetura/visao-geral.md`) |
| 0002 | Camadas View→Service→Repository | aceito |
| — | *(adicionar conforme decisões forem tomadas)* | |

> Registre uma ADR sempre que fizer uma escolha difícil de reverter (banco, auth, multi-tenant, mensageria).
