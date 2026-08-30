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


class PlanCode(models.TextChoices):
    ASSOCIADO = "associado", "Associado"
    BARBEARIA = "barbearia", "Mensalista Barbearia"


def plan_price(code: str) -> Decimal:
    """Valor do plano, de ASSOCIADO_FEE/BARBEARIA_FEE no .env.

    Lido a cada uso, nunca importado — mudar o valor não exige mexer no
    código, e a mensalidade já gerada fica congelada (snapshot em
    Due.amount).
    """
    if code == PlanCode.ASSOCIADO:
        return Decimal(str(settings.ASSOCIADO_FEE))
    if code == PlanCode.BARBEARIA:
        return Decimal(str(settings.BARBEARIA_FEE))
    raise ValueError(f"Plano desconhecido: {code}")


# Postos que já foram promovidos de "Sd" pro par EP/EV, mas ainda não
# tiveram o cadastro corrigido, ficam de fora até alguém reclassificar —
# não dá pra adivinhar qual dos dois planos vale (RN da Fase 2).
_UNCLASSIFIED_RANKS = frozenset({"Sd"})
_BARBEARIA_ONLY_RANKS = frozenset({"Sd EV"})
_BOTH_PLANS_RANKS = frozenset({"Sd EP", "Cb"})


def eligible_plans_for(posto_graduacao: str) -> frozenset[str]:
    """Quais PlanCode um posto pode assinar (RN da Fase 2 — ver spec)."""
    if not posto_graduacao or posto_graduacao in _UNCLASSIFIED_RANKS:
        return frozenset()
    if posto_graduacao in _BARBEARIA_ONLY_RANKS:
        return frozenset({PlanCode.BARBEARIA})
    if posto_graduacao in _BOTH_PLANS_RANKS:
        return frozenset({PlanCode.ASSOCIADO, PlanCode.BARBEARIA})
    return frozenset({PlanCode.ASSOCIADO})


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
    plan = models.CharField(max_length=20, choices=PlanCode.choices)
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
