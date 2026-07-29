# Patrimonia — ERP Patrimonial SaaS

Plataforma de gestão patrimonial multi-tenant onde **cada bem tem uma agenda própria**
(estilo Booksy): `Pesquisar → Reservar → Aprovar → Cautela assinada → Devolução → Inspeção`.

> Documentação completa em [`docs/`](docs/INDEX.md). Regras para o agente em [`.claude/CLAUDE.md`](.claude/CLAUDE.md).

## Stack
React + Vite + TS + Tailwind + PWA · Django + DRF · PostgreSQL · Redis + Celery · Docker.
Detalhes: [`docs/arquitetura/stack.md`](docs/arquitetura/stack.md).

## Estrutura
```
backend/    Django (camadas View→Service→Repository→Model, multi-tenant, auditoria)
frontend/   React PWA (React Query, Tailwind)
docs/        PRD, arquitetura, domínio, módulos, API, processo
docker-compose.yml
```

## Subir com Docker (recomendado)
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build
```
- API: http://localhost:8000/api/docs/ (Swagger)
- Front: http://localhost:5173

## Desenvolvimento local (sem Docker)

### Backend
```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python manage.py migrate
python manage.py runserver
```
Qualidade: `ruff check .` · `mypy core apps config` · `pytest`

Sem Postgres local, o `dev` usa SQLite automaticamente (ver `config/settings/dev.py`).

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Qualidade: `npm run lint` · `npm run build`

## Princípios inegociáveis
Multi-tenant sempre · regra de negócio só no Service · auditoria em ações sensíveis · API First.
Ver [`docs/processo/definition-of-done.md`](docs/processo/definition-of-done.md).

## Roadmap
[`docs/processo/sprints.md`](docs/processo/sprints.md). **Sprint 0 (fundação) concluído.**
