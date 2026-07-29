# Módulo: Agenda ⛔

## Objetivo
Diferencial do produto: **cada bem tem uma agenda própria** (disponibilidade + reservas), com visão diária/semanal/mensal estilo Google Calendar / Booksy.

## Entidades
`Availability`, `Booking`, `Asset`. Ver `dominio/entidades.md`.

## Casos de uso (a detalhar)
- [ ] UC-A1 Definir disponibilidade do bem (janelas, slots).
- [ ] UC-A2 Visualizar agenda (dia/semana/mês) por bem, categoria ou local.
- [ ] UC-A3 Buscar bem disponível em um período.

## Regras
- [ ] **Sem sobreposição** de reservas aprovadas para o mesmo bem (invariante crítica — testar).
- [ ] Fuso horário do tenant; slots configuráveis.

## Endpoints (a definir)
`GET /api/assets/{id}/availability` · `GET /api/agenda?view=week&scope=` .

## Referência de UX
Google Calendar (grade), Booksy / Microsoft Bookings (seleção de slot).

## A detalhar (TODO)
- [ ] Regras de antecedência mínima / máxima de reserva.
- [ ] Bloqueios (feriados, manutenção) sobre a agenda.
