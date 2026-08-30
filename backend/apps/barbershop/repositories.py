from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from django.db import models

from core.repositories import BaseRepository

from .models import (
    ACTIVE_APPOINTMENT_STATUSES,
    QUOTA_APPOINTMENT_STATUSES,
    Appointment,
    Barber,
    BarberSchedule,
    BarberTimeOff,
    PublicAgendaLink,
)


class BarberRepository(BaseRepository[Barber]):
    model = Barber

    def active(self) -> models.QuerySet[Barber]:
        return self.query().filter(is_active=True)


class BarberScheduleRepository(BaseRepository[BarberSchedule]):
    model = BarberSchedule

    def for_barber(self, barber_id: UUID | str) -> models.QuerySet[BarberSchedule]:
        return self.query().filter(barber_id=barber_id)

    def for_weekday(
        self, *, barber_id: UUID | str, weekday: int
    ) -> models.QuerySet[BarberSchedule]:
        return self.for_barber(barber_id).filter(weekday=weekday)


class BarberTimeOffRepository(BaseRepository[BarberTimeOff]):
    model = BarberTimeOff

    def for_barber(self, barber_id: UUID | str) -> models.QuerySet[BarberTimeOff]:
        return self.query().filter(barber_id=barber_id)

    def is_off(self, *, barber_id: UUID | str, day: date) -> bool:
        return self.covering(barber_id=barber_id, day=day).exists()

    def covering(self, *, barber_id: UUID | str, day: date) -> models.QuerySet[BarberTimeOff]:
        """Folgas cujo período engloba o dia."""
        return self.for_barber(barber_id).filter(start_date__lte=day, end_date__gte=day)

    def overlapping(
        self,
        *,
        barber_id: UUID | str,
        start_date: date,
        end_date: date,
        exclude_id: UUID | str | None = None,
    ) -> models.QuerySet[BarberTimeOff]:
        """Folgas que cruzam o período — dois recessos não podem se sobrepor."""
        qs = self.for_barber(barber_id).filter(
            start_date__lte=end_date, end_date__gte=start_date
        )
        if exclude_id is not None:
            qs = qs.exclude(id=exclude_id)
        return qs


class PublicAgendaLinkRepository(BaseRepository[PublicAgendaLink]):
    model = PublicAgendaLink

    def active(self) -> models.QuerySet[PublicAgendaLink]:
        return self.query().filter(is_active=True)


class AppointmentRepository(BaseRepository[Appointment]):
    model = Appointment

    def overlapping(
        self,
        *,
        barber_id: UUID | str,
        start_at: datetime,
        end_at: datetime,
        exclude_id: UUID | str | None = None,
    ) -> models.QuerySet[Appointment]:
        """Agendamentos ativos do barbeiro que cruzam [start_at, end_at) — RN-BB1."""
        qs = self.query().filter(
            barber_id=barber_id,
            status__in=ACTIVE_APPOINTMENT_STATUSES,
            start_at__lt=end_at,
            end_at__gt=start_at,
        )
        if exclude_id is not None:
            qs = qs.exclude(id=exclude_id)
        return qs

    def on_day(self, *, barber_id: UUID | str, day: date) -> models.QuerySet[Appointment]:
        return self.query().filter(
            barber_id=barber_id,
            status__in=ACTIVE_APPOINTMENT_STATUSES,
            start_at__date=day,
        )

    def month_usage(
        self,
        *,
        customer_id: UUID | str,
        year: int,
        month: int,
        exclude_id: UUID | str | None = None,
    ) -> models.QuerySet[Appointment]:
        """Cortes de assinante que a pessoa já consumiu no mês (cancelado não conta)."""
        qs = self.query().filter(
            customer_id=customer_id,
            is_subscriber=True,
            status__in=QUOTA_APPOINTMENT_STATUSES,
            start_at__year=year,
            start_at__month=month,
        )
        if exclude_id is not None:
            qs = qs.exclude(id=exclude_id)
        return qs
