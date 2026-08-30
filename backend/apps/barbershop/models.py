"""Barbearia: barbeiro, grade semanal de trabalho, folgas e agendamentos.

Invariante-chave (RN-BB1): dois agendamentos ativos nunca se sobrepõem para o
mesmo barbeiro. Regras de assinante e preço vivem no BarbershopService.
"""
from __future__ import annotations

import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.scheduling.models import Weekday
from core.models import TenantScopedModel

# Assinante (Associado Full ou Assinatura Barbearia, ver apps.finance) tem
# direito a 4 cortes por mês; quem não é assinante paga por corte.
SUBSCRIBER_MONTHLY_LIMIT = 4


def walk_in_price() -> Decimal:
    """Preço do corte avulso, de WALK_IN_PRICE no .env (padrão R$ 15,00).

    Lido a cada uso, não na importação: mudar o valor não pode exigir mexer no
    código, e o preço de cada agendamento já fica congelado no ato da marcação.
    """
    return Decimal(str(settings.WALK_IN_PRICE))

# Remarcar e cancelar valem até 10 minutos antes da hora marcada — depois disso
# o barbeiro já está com o horário reservado e o corte conta.
CHANGE_CUTOFF_MINUTES = 10


class Barber(TenantScopedModel):
    """Barbeiro é cadastro, não usuário do sistema — quem opera é a administração."""

    name = models.CharField(max_length=120)
    nickname = models.CharField(max_length=60, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    # Foto como data URI (base64), mesmo padrão de Asset.photo_data.
    photo_data = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "barber"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.nickname or self.name


class BarberSchedule(TenantScopedModel):
    """Janela semanal recorrente em que o barbeiro atende."""

    barber = models.ForeignKey(Barber, on_delete=models.CASCADE, related_name="schedules")
    weekday = models.IntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_minutes = models.PositiveIntegerField(default=30)

    class Meta:
        db_table = "barber_schedule"
        ordering = ["weekday", "start_time"]

    def __str__(self) -> str:
        return f"{self.barber} {self.get_weekday_display()} {self.start_time}-{self.end_time}"


class BarberTimeOff(TenantScopedModel):
    """Período em que o barbeiro não atende, mesmo caindo na grade semanal.

    Um dia só é um período com início igual ao fim — assim férias e feriado
    usam a mesma estrutura, e apagar um recesso inteiro é apagar uma linha.
    """

    barber = models.ForeignKey(Barber, on_delete=models.CASCADE, related_name="time_off")
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=120, blank=True)

    class Meta:
        db_table = "barber_time_off"
        ordering = ["start_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="ck_time_off_range",
            )
        ]

    def __str__(self) -> str:
        if self.start_date == self.end_date:
            return f"{self.barber} folga {self.start_date:%d/%m/%Y}"
        return f"{self.barber} folga {self.start_date:%d/%m} a {self.end_date:%d/%m/%Y}"

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1


class AppointmentStatus(models.TextChoices):
    # Avulso nasce aqui: segura o horário, mas não vale corte até o Pix cair.
    AWAITING_PAYMENT = "awaiting_payment", "Aguardando pagamento"
    SCHEDULED = "scheduled", "Agendado"
    # ACTIVE nunca é gravado: o relógio é que diz se o atendimento está em curso.
    # Ver BarbershopService.effective_status.
    ACTIVE = "active", "Ativo"
    COMPLETED = "completed", "Finalizado"
    CANCELLED = "cancelled", "Cancelado"
    NO_SHOW = "no_show", "Não compareceu"


# Situações que seguram o horário (bloqueiam sobreposição) — RN-BB1. O avulso
# à espera do Pix também segura, senão o horário seria vendido duas vezes; se o
# prazo do Pix vencer, o agendamento é cancelado e o horário volta (RN-BB8).
ACTIVE_APPOINTMENT_STATUSES = (
    AppointmentStatus.SCHEDULED,
    AppointmentStatus.AWAITING_PAYMENT,
)

# Situações que consomem a cota mensal do assinante. SCHEDULED entra porque o
# horário marcado já reserva o corte; cancelar antes da hora devolve.
QUOTA_APPOINTMENT_STATUSES = (AppointmentStatus.SCHEDULED, AppointmentStatus.COMPLETED)


class Appointment(TenantScopedModel):
    barber = models.ForeignKey(Barber, on_delete=models.PROTECT, related_name="appointments")
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="barber_appointments"
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    is_subscriber = models.BooleanField(default=False)
    # Preço congelado no ato: se a tabela mudar, o histórico continua verdadeiro.
    price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    # Pago com crédito do próprio usuário, sem Pix nem cobrança nova.
    paid_with_credit = models.BooleanField(default=False)
    # Cobrança Pix do avulso. Assinante não tem cobrança.
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    status = models.CharField(
        max_length=20, choices=AppointmentStatus.choices, default=AppointmentStatus.SCHEDULED
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "appointment"
        ordering = ["-start_at"]
        indexes = [models.Index(fields=["barber", "start_at"])]

    def __str__(self) -> str:
        return f"{self.barber} {self.start_at:%d/%m %H:%M}"


def _gen_public_agenda_token() -> str:
    return secrets.token_urlsafe(24)


class PublicAgendaLink(TenantScopedModel):
    """Link público (sem login) pra qualquer barbeiro ver a agenda do dia —
    um por organização. Regenerar desativa o token antigo na hora (RN-BB12,
    ver BarbershopService.regenerate_public_agenda_link)."""

    token = models.CharField(max_length=64, unique=True, default=_gen_public_agenda_token)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "barbershop_public_agenda_link"

    def __str__(self) -> str:
        return f"Agenda pública — {self.tenant_id}"
