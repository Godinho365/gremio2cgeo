# Definition of Done ✅

Uma tarefa/feature só está **pronta** quando:

## Código
- [ ] Segue as camadas (View→Service→Repository→Model); regra só no Service.
- [ ] Filtra por `tenant_id` em toda query.
- [ ] Sem duplicação (DRY); reutiliza o que já existe.
- [ ] Lint (ruff/eslint) e tipos (mypy/tsc strict) sem erros.

## Testes
- [ ] Testes para as regras críticas afetadas (referenciar `RN-xx`).
- [ ] Teste de isolamento multi-tenant quando aplicável.
- [ ] Pipeline CI verde.

## API / Contrato
- [ ] OpenAPI atualizado (drf-spectacular) e coerente com `api/convencoes.md`.
- [ ] Erros no formato padrão.

## Auditoria e segurança
- [ ] Ações sensíveis geram `AuditLog`.
- [ ] Permissões por perfil verificadas.

## Documentação
- [ ] Doc do módulo (`docs/modulos/<nome>.md`) atualizado; status ajustado no `docs/INDEX.md`.
- [ ] Mudança relevante registrada (e ADR se for decisão arquitetural).

## UX (quando houver UI)
- [ ] Mobile First, responsivo, acessível.
- [ ] Estados de loading/erro/vazio tratados.
