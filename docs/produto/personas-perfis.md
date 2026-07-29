# Personas e Perfis (RBAC) 🟡

## Perfis (Roles)
| Perfil | Quem é | Faz |
|---|---|---|
| **Administrador** | Gestor da conta/tenant | Configura organização, usuários, categorias, locais; tudo. |
| **Diretor(a) Patrimonial** | Responsável do Art.30 | Cataloga bens, emite/devolve cautelas, abre/fecha inventário, manutenção, aprova reservas. |
| **Inventariante** | Operador de campo | Escaneia QR, confere bens em inventário, move bens de local. |
| **Usuário** | Associado | Pesquisa, reserva, recebe bem sob cautela (assina como holder), devolve. |
| **Auditor** | Fiscalização | Leitura total + relatórios e AuditLog; não altera nada. |

## Matriz de permissões (resumo)
| Ação | Admin | Diretor | Invent. | Usuário | Auditor |
|---|:-:|:-:|:-:|:-:|:-:|
| Config. organização/usuários | ✓ | – | – | – | – |
| Cadastrar/editar bem | ✓ | ✓ | – | – | – |
| Mover bem de local | ✓ | ✓ | ✓ | – | – |
| Reservar | ✓ | ✓ | – | ✓ | – |
| Aprovar reserva | ✓ | ✓ | – | – | – |
| Emitir/devolver cautela | ✓ | ✓ | – | – | – |
| Assinar cautela (holder) | – | – | – | ✓ | – |
| Inventário (abrir/fechar) | ✓ | ✓ | – | – | – |
| Inventário (conferir campo) | ✓ | ✓ | ✓ | – | – |
| Manutenção | ✓ | ✓ | – | – | – |
| Relatórios + AuditLog | ✓ | ✓ | ✓* | ✓* | ✓ |

\* escopo reduzido (próprios dados). Detalhe por módulo em `modulos/<nome>.md`.

## A detalhar (TODO)
- [ ] Permissões finas (por local/categoria).
- [ ] Perfis customizáveis por tenant.
