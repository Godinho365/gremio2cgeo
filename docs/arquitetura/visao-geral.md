# Arquitetura — Visão Geral ✅

## Princípios
Clean Architecture + DDD pragmático. A regra de negócio não depende de framework, banco ou HTTP.

## Camadas (backend)

```
HTTP  →  View / Serializer   (DRF: entrada/saída, validação de formato, authz)
             │
         Service             (regra de negócio, orquestração, transações)  ← ÚNICO lugar de lógica
             │
         Repository          (acesso a dados; esconde o ORM)
             │
         Model / ORM         (Django Models, migrations)
             │
         PostgreSQL
```

**Regras:**
- View **não** contém regra de negócio — só traduz HTTP ↔ Service.
- Service **não** conhece `request`/`response`. Recebe dados, retorna dados/DTOs.
- Repository **não** contém regra — só consultas/persistência. Toda query filtra `tenant_id`.
- Model **não** contém regra complexa — só validações de campo e relacionamentos.

## Multi-tenant (SaaS)
- Estratégia: **shared database, shared schema** com `tenant_id` em todas as tabelas.
- Isolamento garantido em camada de Repository (base repo injeta filtro de tenant) — nunca confiar só na view.
- Tenant resolvido por middleware (subdomínio ou claim do JWT) → disponível no contexto do request.
- Escrever teste que prova que Tenant A não lê dados de Tenant B.

## Assíncrono (Celery + Redis)
Jobs: geração de PDF de termo, notificações, marcação de cautelas atrasadas, cálculo de depreciação, relatórios pesados, lembretes de inventário.

## Frontend
- React + Vite + TS, **Mobile First** e **PWA** (offline para inventário em campo — escanear QR sem rede e sincronizar depois).
- Estado servidor: React Query. Componentes reutilizáveis (design system próprio).
- UX inspirada em Google Calendar (agenda), Booksy/Microsoft Bookings (reserva por slot).

## Segurança
- JWT (access curto + refresh). RBAC por Perfil (ver `produto/personas-perfis.md`).
- AuditLog imutável para ações sensíveis.
- Rate limiting, validação server-side sempre, uploads escaneados.

## Padrões de projeto usados
Repository, Service Layer, DTO, Factory (geração de asset_tag), State (ciclo do bem), Observer/eventos (AuditLog, notificações).

## Estrutura de pastas (proposta)
```
backend/
  apps/<modulo>/
    api/          # views, serializers, urls
    services/     # regra de negócio
    repositories/ # acesso a dados
    models.py
    tests/
  core/           # base repo/service, multi-tenant, auditoria
frontend/
  src/
    features/<modulo>/
    components/    # design system
    lib/          # api client, react-query
```

Decisões formais e trade-offs: `arquitetura/adr/README.md`.
