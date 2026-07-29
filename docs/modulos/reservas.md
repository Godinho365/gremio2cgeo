# Módulo: Reservas ⛔

## Objetivo
Permitir que usuários solicitem o uso de um bem por período, com fluxo de aprovação, integrando agenda → cautela.

## Entidades
`Booking`, `Availability`, `Asset`, `User`. Ver `dominio/entidades.md`.

## Casos de uso (a detalhar)
- [ ] UC-R1 Solicitar reserva (período disponível).
- [ ] UC-R2 Aprovar/recusar (Diretor).
- [ ] UC-R3 Cancelar reserva.
- [ ] UC-R4 Reserva aprovada → gera cautela (`modulos/cautelas.md`).

## Regras
- [ ] Reserva só em slot disponível e sem conflito.
- [ ] Aprovação obrigatória configurável por categoria/bem.
- [ ] Estados: pendente → aprovada/recusada → concluída/cancelada.

## Endpoints (a definir)
`POST /api/bookings` · `POST /api/bookings/{id}/approve` · `POST /api/bookings/{id}/cancel`.
