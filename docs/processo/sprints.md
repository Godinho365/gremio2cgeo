# Roadmap / Sprints ✅

Cada sprint entrega valor vertical (API + UI + testes) e respeita a `definition-of-done.md`.

## Sprint 0 — Fundação
Setup: Docker, Django+DRF, Postgres, Redis/Celery, React+Vite+TS, CI, OpenAPI. Multi-tenant base + AuditLog base. Base repo/service.
**Pronto quando**: app sobe via docker-compose, pipeline verde, teste de isolamento tenant passa.

## Sprint 1 — Auth, usuários e permissões
JWT, perfis/RBAC (`produto/personas-perfis.md`), CRUD de usuários.

## Sprint 2 — Patrimônio + etiquetas (Art.30 a)
Categorias, locais hierárquicos, aquisição, CRUD de bem, geração de `asset_tag` e QR. Importação em massa.

## Sprint 3 — Agenda (Booksy)
Disponibilidade + visão dia/semana/mês. Busca de bem disponível. Invariante anti-sobreposição.

## Sprint 4 — Reservas + Cautelas (Art.30 d)
Fluxo reserva→aprovação→cautela assinada→devolução→inspeção. PDF do termo. Cautela atrasada (Celery).

## Sprint 5 — Inventário (Art.30 b)
Abrir/fechar, conferência por QR, **PWA offline** + sync, divergências, relatório de conformidade.

## Sprint 6 — Manutenção (Art.30 c)
Ordens preventiva/corretiva/proteção; integração com inspeção; plano preventivo recorrente.

## Sprint 7 — Dashboard
KPIs e alertas (cautelas atrasadas, divergências, manutenção). Cache Redis.

## Sprint 8 — Relatórios
Exportações PDF/xlsx oficiais (Art.30 a-d) em background.

## Sprint 9 — Refino PWA + hardening
Offline completo, performance, segurança, acessibilidade.

## Sprint 10 — IA / auditoria inteligente
Detecção de anomalias (bens sumindo, cautelas recorrentes vencidas), sugestões. Ver skill `claude-api` antes de integrar LLM.

> Sequência guia prioridade, não prazo. Reordene conforme validação com o usuário.
