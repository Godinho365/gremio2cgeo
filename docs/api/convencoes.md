# Convenções de API 🟡

API First: o contrato (OpenAPI via drf-spectacular) é a fonte da verdade. Gere o spec antes de implementar.

## Padrões
- Base: `/api/`. Recursos no **plural**: `/api/assets`, `/api/custodies`.
- Métodos: `GET` (ler), `POST` (criar/ação), `PATCH` (atualização parcial), `DELETE` (soft delete).
- Ações não-CRUD como sub-recurso: `POST /api/custodies/{id}/return`.
- IDs: UUID. Datas: ISO-8601 com timezone.
- Multi-tenant: tenant vem do JWT/middleware, **nunca** por parâmetro do cliente.

## Respostas
- Sucesso: objeto do recurso ou `{ "data": [...], "meta": {...} }` para listas.
- Paginação: `?page=&page_size=` → `meta: { page, page_size, total }`.
- Filtros/ordenação: query params (`?status=&category=&ordering=-created_at`).

## Erros (padrão consistente)
```json
{ "error": { "code": "validation_error", "message": "...", "fields": { "due_at": ["obrigatório"] } } }
```
Status: 400 validação · 401 não autenticado · 403 sem permissão · 404 · 409 conflito (ex: sobreposição de reserva) · 422 regra de negócio.

## Versionamento
Prefixo por versão maior quando quebrar contrato: `/api/v1/`. Evitar breaking changes; preferir adição.

## Segurança
`Authorization: Bearer <jwt>`. Rate limit por usuário/tenant. Validação server-side sempre.

## A detalhar (TODO)
- [ ] Contrato completo de cada endpoint (request/response) — gerar do drf-spectacular.
- [ ] Webhooks/eventos externos, se houver.
