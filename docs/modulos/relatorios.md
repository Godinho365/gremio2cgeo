# Módulo: Relatórios ⛔

## Objetivo
Emitir relatórios oficiais e exportações para prestação de contas e conformidade estatutária.

## Relatórios candidatos (a validar)
- [ ] Relação de bens (inventário patrimonial) — Art.30 a/b.
- [ ] Termos de cautela e responsabilidade por período/pessoa/bem — Art.30 d.
- [ ] Relatório de conformidade de inventário (divergências) — Art.30 b.
- [ ] Histórico de manutenção e custos — Art.30 c.
- [ ] Depreciação / valor patrimonial.

## Regras
- [ ] Exportação PDF e planilha (xlsx/csv).
- [ ] Geração pesada em background (Celery); download assíncrono.
- [ ] Respeita tenant e permissões; toda emissão gera AuditLog.
