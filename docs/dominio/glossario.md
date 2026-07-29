# Glossário do Domínio ✅

Linguagem ubíqua (DDD). Use **estes termos** em código, API e conversa. `código` = nome sugerido em inglês.

| Termo (PT) | `code` | Definição |
|---|---|---|
| Organização / Tenant | `Tenant` | Instituição cliente do SaaS. Raiz do isolamento de dados. |
| Usuário | `User` | Pessoa autenticada, pertence a um Tenant, tem um ou mais Perfis. |
| Perfil | `Role` | Conjunto de permissões (Admin, Diretor Patrimonial, Inventariante, Usuário, Auditor). |
| Bem / Patrimônio | `Asset` | Item patrimonial catalogado. Unidade central do sistema. |
| Numeração patrimonial | `asset_tag` | Identificador único e legível do bem (ex: `PAT-2026-000123`). |
| Etiqueta / QR | `AssetLabel` | Etiqueta física (QR/código de barras) que aponta para o `asset_tag`. |
| Categoria | `Category` | Classificação do bem (móvel, TI, veículo…), pode ser hierárquica. |
| Localização | `Location` | Local físico hierárquico (Unidade > Prédio > Andar > Sala). |
| Fornecedor | `Supplier` | Origem de aquisição por compra. |
| Aquisição | `Acquisition` | Registro de como o bem entrou (compra ou doação) — Art.30 a. |
| Estado de conservação | `condition` | novo / bom / regular / ruim / inservível. |
| Situação do bem | `status` | disponível / reservado / em uso (cautelado) / manutenção / baixado. |
| Disponibilidade | `Availability` | Janela em que um bem pode ser reservado (agenda do bem). |
| Reserva | `Booking` | Pedido de uso de um bem em um período; pode exigir aprovação. |
| Cautela | `Custody` | Termo de responsabilidade assinado ao entregar o bem — Art.30 d. |
| Termo de responsabilidade | `CustodyTerm` | Documento gerado/assinado da cautela. |
| Devolução | `Return` | Ato de retornar o bem cautelado. |
| Inspeção | `Inspection` | Conferência do estado do bem na devolução — Art.30 d. |
| Inventário | `Inventory` | Levantamento periódico para conferir bens x locais — Art.30 b. |
| Item de inventário | `InventoryItem` | Contagem/conferência de um bem dentro de um inventário. |
| Divergência | `Discrepancy` | Diferença entre esperado e encontrado no inventário. |
| Manutenção | `Maintenance` | Ordem de conservação/reparo/proteção do bem — Art.30 c. |
| Baixa | `Writeoff` | Desativação definitiva do bem (venda, doação, descarte). |
| Anexo | `Attachment` | Foto, PDF ou assinatura vinculada a um registro. |
| Log de auditoria | `AuditLog` | Registro imutável de ação sensível (quem/o quê/quando). |

## Estados do Bem (máquina de estados)
`disponível → reservado → em_uso → (devolução+inspeção) → disponível`
Ramificações: `→ manutenção → disponível` · `→ baixado` (terminal).
Detalhe e transições permitidas: `dominio/regras-negocio.md`.
