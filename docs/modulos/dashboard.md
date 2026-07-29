# Módulo: Dashboard ⛔

## Objetivo
Visão executiva do patrimônio: indicadores e alertas acionáveis.

## KPIs candidatos (a validar)
- [ ] Total de bens / valor patrimonial (aquisição × atual).
- [ ] Bens por situação (disponível/em uso/manutenção/baixado).
- [ ] Cautelas ativas e **atrasadas** (Art.30 d).
- [ ] Divergências do último inventário (Art.30 b).
- [ ] Ordens de manutenção abertas (Art.30 c).
- [ ] Taxa de utilização dos bens (via agenda).

## Regras
- [ ] Respeita permissões e tenant (só dados da organização).
- [ ] Widgets consomem endpoints de agregação (cache em Redis).

## Referência de UX
Cards de KPI + gráficos. Ver skill `dataviz` antes de criar qualquer gráfico.
