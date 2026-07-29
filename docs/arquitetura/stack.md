# Stack Tecnológica ✅

> Fixe versões maiores aqui. Detalhe de libs menores fica no `package.json`/`pyproject.toml`.

## Frontend
| Item | Escolha | Por quê |
|---|---|---|
| Framework | React 18+ | ecossistema, PWA maduro |
| Build | Vite | dev rápido |
| Linguagem | TypeScript (strict) | segurança de tipos |
| Estilo | Tailwind CSS | Mobile First rápido, consistente |
| Estado servidor | React Query (TanStack) | cache/sync de API |
| PWA | Vite PWA plugin + Workbox | offline p/ inventário em campo |
| Formulários | React Hook Form + Zod | validação client alinhada ao contrato |
| Testes | Vitest + Testing Library + Playwright (e2e) | |

## Backend
| Item | Escolha | Por quê |
|---|---|---|
| Framework | Django 5 + Django REST Framework | maturidade, admin, ORM |
| Auth | JWT (SimpleJWT) | stateless, mobile-friendly |
| Docs API | drf-spectacular (OpenAPI) | API First |
| Testes | pytest + pytest-django + factory_boy | |
| Qualidade | ruff + mypy | lint + tipos |

## Dados e Infra
| Item | Escolha |
|---|---|
| Banco | PostgreSQL 16 |
| Cache/broker | Redis |
| Filas | Celery + Celery Beat |
| Storage | S3-compatível (uploads, termos, fotos) |
| Container | Docker + docker-compose (dev) |
| CI | GitHub Actions (lint, test, build) |

## Convenções de versão
- Node LTS, Python 3.12+.
- Uma feature = uma branch; PR com testes verdes obrigatório.
