# Arquitetura

Frontend:
- React
- Vite
- TypeScript
- Tailwind
- PWA

Backend:
- Django
- Django REST Framework

Banco:
- PostgreSQL

Infra:
- Docker
- Redis
- Celery

Fluxo:

React
  |
API REST
  |
Services
  |
Repositories
  |
PostgreSQL

Módulo Agenda:
Cada patrimônio possui disponibilidade, reservas, cautelas e manutenção.
