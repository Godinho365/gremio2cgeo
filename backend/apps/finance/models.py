"""Financeiro — mensalidades (Fase 1: núcleo).

BillingProfile: quem está na relação financeira e as regras dele (dia de
vencimento, desde quando). Due: uma mensalidade de um mês específico — no
máximo uma por (billing_profile, period). FinanceCredit: extrato de crédito
por resto de pagamento, mesmo padrão do CreditEntry da barbearia (saldo é a
soma das linhas, nunca um campo solto).
"""
from __future__ import annotations

import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.payments.models import Payment
from core.models import TenantScopedModel


# Vencimento é o mesmo dia pra todo mundo — travado, não configurável por
# perfil (RN pedida: facilita conferência e o comparativo mensal por
# competência). Ver migração 0008 pro backfill dos perfis já existentes.
DEFAULT_DUE_DAY = 5


class PlanCode(models.TextChoices):
    # O código interno ("associado"/"barbearia") não muda — só o rótulo que
    # aparece pra pessoa. Mudar o código exigiria migração de dados; o rótulo
    # é só metadado de exibição.
    ASSOCIADO = "associado", "Associado Full"
    BARBEARIA = "barbearia", "Assinatura Barbearia"


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
    due_day = models.PositiveSmallIntegerField(default=DEFAULT_DUE_DAY)
    started_period = models.DateField()
    is_active = models.BooleanField(default=True)
    financial_status = models.CharField(
        max_length=20, choices=FinancialStatus.choices, default=FinancialStatus.UP_TO_DATE
    )
    last_payment_at = models.DateTimeField(null=True, blank=True)
    # Pix de autoatendimento em aberto — quem confirma é sempre o provedor
    # (webhook/tarefa periódica), nunca o clique do usuário (RN-P2).
    pending_payment = models.ForeignKey(
        Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

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


def _gen_invite_token() -> str:
    return secrets.token_urlsafe(24)


def _default_invite_expiry():
    return timezone.now() + timedelta(days=settings.ASSOCIADO_INVITE_DAYS)


class AssociadoInvite(TenantScopedModel):
    """Convite de autoatendimento pro plano Associado (Cb/Sd EP).

    Gerado pelo admin, consumido pelo próprio usuário — ver
    FinanceService.generate_associado_invite/accept_associado_invite.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="associado_invites"
    )
    token = models.CharField(max_length=64, unique=True, default=_gen_invite_token)
    expires_at = models.DateTimeField(default=_default_invite_expiry)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "associado_invite"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Convite Associado — {self.user}"

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and timezone.now() <= self.expires_at
