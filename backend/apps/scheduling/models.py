"""Agenda domain: cada bem tem disponibilidade e reservas (estilo Booksy).

Ver docs/modulos/agenda.md e docs/modulos/reservas.md. Invariante-chave:
sem sobreposição de reservas ativas para o mesmo bem (RN-B1).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.assets.models import Asset
from core.models import TenantScopedModel


class Weekday(models.IntegerChoices):
    MONDAY = 0, "Segunda"
    TUESDAY = 1, "Terça"
    WEDNESDAY = 2, "Quarta"
    THURSDAY = 3, "Quinta"
    FRIDAY = 4, "Sexta"
    SATURDAY = 5, "Sábado"
    SUNDAY = 6, "Domingo"


class Availability(TenantScopedModel):
    """Janela semanal recorrente em que um bem pode ser reservado."""

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="availabilities")
    weekday = models.IntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_minutes = models.PositiveIntegerField(default=60)

    class Meta:
        db_table = "availability"
        ordering = ["weekday", "start_time"]

    def __str__(self) -> str:
        day = self.get_weekday_display()
        return f"{self.asset.asset_tag} {day} {self.start_time}-{self.end_time}"


class BookingStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    APPROVED = "approved", "Aprovada"
    REJECTED = "rejected", "Recusada"
    CANCELLED = "cancelled", "Cancelada"
    COMPLETED = "completed", "Concluída"


# Statuses that hold a time slot (block overlaps) — RN-B1.
ACTIVE_BOOKING_STATUSES = (BookingStatus.PENDING, BookingStatus.APPROVED)


class Booking(TenantScopedModel):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="bookings")
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings"
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=BookingStatus.choices, default=BookingStatus.PENDING
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_bookings",
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "booking"
        ordering = ["-start_at"]
        indexes = [models.Index(fields=["asset", "start_at"])]

    def __str__(self) -> str:
        return f"{self.asset.asset_tag} {self.start_at:%d/%m %H:%M}"
