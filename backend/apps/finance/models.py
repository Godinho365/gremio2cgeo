"""Financeiro — mensalidades (Fase 1: núcleo).

BillingProfile: quem está na relação financeira e as regras dele (dia de
vencimento, desde quando). Due: uma mensalidade de um mês específico — no
máximo uma por (billing_profile, period). FinanceCredit: extrato de crédito
por resto de pagamento, mesmo padrão do CreditEntry da barbearia (saldo é a
soma das linhas, nunca um campo solto).
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.payments.models import Payment
from core.models import TenantScopedModel


def membership_fee() -> Decimal:
    """Valor da mensalidade, de MEMBERSHIP_FEE no .env (padrão R$ 100,00).

    Lido a cada uso: mudar o valor não exige mexer no código, e a mensalidade
    já gerada fica congelada (snapshot em Due.amount).
    """
    return Decimal(str(settings.MEMBERSHIP_FEE))


class FinancialStatus(models.TextChoices):
    UP_TO_DATE = "up_to_date", "Em dia"
    PAID_IN_ADVANCE = "paid_in_advance", "Pago antecipadamente"
    DUE_SOON = "due_soon", "Próximo do vencimento"
    DUE_TODAY = "due_today", "Vencendo hoje"
    OVERDUE = "overdue", "Vencido"
    DELINQUENT = "delinquent", "Inadimplente"


class BillingProfile(TenantScopedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="billing_profile"
    )
    due_day = models.PositiveSmallIntegerField()
    started_period = models.DateField()
    is_active = models.BooleanField(default=True)
    financial_status = models.CharField(
        max_length=20, choices=FinancialStatus.choices, default=FinancialStatus.UP_TO_DATE
    )
    last_payment_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "billing_profile"

    def __str__(self) -> str:
        return f"Mensalidade de {self.user}"


class DueStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    DUE_SOON = "due_soon", "Próximo do vencimento"
    DUE_TODAY = "due_today", "Vencendo hoje"
    OVERDUE = "overdue", "Vencido"
    DELINQUENT = "delinquent", "Inadimplente"
    PAID = "paid", "Pago"


OPEN_DUE_STATUSES = (
    DueStatus.PENDING,
    DueStatus.DUE_SOON,
    DueStatus.DUE_TODAY,
    DueStatus.OVERDUE,
    DueStatus.DELINQUENT,
)


class Due(TenantScopedModel):
    billing_profile = models.ForeignKey(
        BillingProfile, on_delete=models.CASCADE, related_name="dues"
    )
    period = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=DueStatus.choices, default=DueStatus.PENDING)
    # True quando liquidada antes do próprio mês (period) começar.
    paid_in_advance = models.BooleanField(default=False)
    settled_by = models.ForeignKey(
        Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="dues_settled"
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "due"
        ordering = ["period"]
        constraints = [
            models.UniqueConstraint(
                fields=["billing_profile", "period"], name="unique_due_period"
            )
        ]
        indexes = [models.Index(fields=["status", "due_date"])]

    def __str__(self) -> str:
        return f"{self.period:%m/%Y} — {self.get_status_display()}"


class FinanceCreditReason(models.TextChoices):
    OVERPAYMENT = "overpayment", "Resto de pagamento"
    CONSUMED = "consumed", "Usado em mensalidade"
    REVERSED = "reversed", "Estornado"
    MANUAL = "manual", "Ajuste da administração"


class FinanceCredit(TenantScopedModel):
    billing_profile = models.ForeignKey(
        BillingProfile, on_delete=models.CASCADE, related_name="credits"
    )
    # Positivo credita, negativo consome/estorna — saldo é sempre a soma.
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=20, choices=FinanceCreditReason.choices)
    payment = models.ForeignKey(
        Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="finance_credits"
    )
    due = models.ForeignKey(
        Due, on_delete=models.SET_NULL, null=True, blank=True, related_name="credit_entries"
    )
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "finance_credit"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        sinal = "+" if self.amount >= 0 else ""
        return f"{sinal}{self.amount} {self.get_reason_display()}"
