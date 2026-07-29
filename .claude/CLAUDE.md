# CLAUDE.md — Patrimonia (ERP Patrimonial SaaS)

> Este arquivo é carregado em **todo** turno. Mantenha-o **curto**.
> Detalhes ficam em `docs/` e são lidos **sob demanda**. Ver mapa: `docs/INDEX.md`.

## O que é
ERP Patrimonial **SaaS multi-tenant**. Cada bem tem uma **agenda própria** (estilo Booksy):
`Pesquisar → Reservar → Aprovar → Cautela (assinada) → Devolução → Inspeção`.

## Regras não-negociáveis
1. **Multi-tenant sempre**: toda query filtra por `tenant_id`. Nunca vaze dados entre organizações.
2. **Camadas**: `View/Serializer → Service → Repository → Model`. Regra de negócio **só** em Service. Sem lógica em views ou models.
3. **Não duplicar** (DRY). Antes de criar, procure algo reutilizável.
4. **Testes** para regra crítica: cautela, inventário, disponibilidade, permissões.
5. **Auditoria**: toda ação sensível gera `AuditLog` (quem, o quê, quando).
6. **API First**: contrato antes do código. Ver `docs/api/convencoes.md`.
7. **Migrations** nunca editadas depois de aplicadas — sempre nova migration.

## Antes de codar
- Leia **só** o doc do módulo/tema em questão (`docs/INDEX.md` lista tudo). Não carregue a documentação inteira.
- Proponha a mudança e o impacto arquitetural antes de implementar mudanças grandes.
- Definição de pronto: `docs/processo/definition-of-done.md`.

## Stack (resumo)
Front: React + Vite + TS + Tailwind + PWA · Back: Django + DRF · Banco: PostgreSQL · Infra: Docker + Redis + Celery.
Detalhes e versões: `docs/arquitetura/stack.md`.

## Módulos
Dashboard · Patrimônio · Agenda · Reservas · Cautelas · Inventário · Manutenção · Relatórios.
Cada um em `docs/modulos/<nome>.md`.

## Idioma
Domínio e docs em **PT-BR**. Código (nomes, comentários) em **inglês**; termos de domínio podem ficar em PT quando não houver tradução clara (ex: `cautela`).
