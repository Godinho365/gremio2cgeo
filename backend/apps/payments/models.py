"""Cobrança — hoje só Pix pelo Mercado Pago, mas o modelo não sabe disso.

Quem fala com o provedor é o gateway (ver gateways/). Aqui fica o que o
sistema precisa saber: quanto, de quem, em que pé está e até quando vale.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import TenantScopedModel


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Aguardando pagamento"
    APPROVED = "approved", "Pago"
    REJECTED = "rejected", "Recusado"
    CANCELLED = "cancelled", "Cancelado"
    EXPIRED = "expired", "Expirado"
    REFUNDED = "refunded", "Devolvido"


# Cobranças que ainda podem virar pagamento.
OPEN_PAYMENT_STATUSES = (PaymentStatus.PENDING,)


class PaymentMethod(models.TextChoices):
    PIX = "pix", "Pix"
    DINHEIRO = "dinheiro", "Dinheiro"
    TRANSFERENCIA = "transferencia", "Transferência"


class Payment(TenantScopedModel):
    provider = models.CharField(max_length=30, default="mercadopago")
    # Id da cobrança no provedor. É por ele que o webhook nos encontra.
    provider_payment_id = models.CharField(max_length=64, blank=True, db_index=True)
    method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.PIX
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments"
    )
    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    # Pix copia-e-cola e a imagem do QR (PNG em base64), como vêm do provedor.
    qr_code = models.TextField(blank=True)
    qr_code_base64 = models.TextField(blank=True)
    ticket_url = models.URLField(blank=True, max_length=500)
    expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    # Situação crua do provedor, para investigar divergência sem depender de log.
    provider_status = models.CharField(max_length=60, blank=True)
    provider_status_detail = models.CharField(max_length=120, blank=True)

    class Meta:
        db_table = "payment"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "expires_at"])]

    def __str__(self) -> str:
        return f"{self.get_method_display()} R$ {self.amount} ({self.get_status_display()})"

    @property
    def is_settled(self) -> bool:
        return self.status == PaymentStatus.APPROVED


class CreditReason(models.TextChoices):
    APPOINTMENT_CANCELLED = "appointment_cancelled", "Horário cancelado"
    USED_IN_APPOINTMENT = "used_in_appointment", "Usado em um horário"
    MANUAL = "manual", "Ajuste da administração"


class CreditEntry(TenantScopedModel):
    """Uma linha do extrato de crédito da pessoa.

    Saldo é a soma das linhas, nunca um número guardado à parte: com um campo
    de saldo, um erro de escrita apaga a origem do dinheiro para sempre. Aqui,
    todo centavo tem uma linha dizendo de onde veio.

    Positivo credita (desistiu de um horário pago), negativo debita (usou o
    crédito para marcar).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="credit_entries"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=30, choices=CreditReason.choices)
    # Cobrança que originou o crédito, quando houve uma.
    payment = models.ForeignKey(
        Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="credit_entries"
    )
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "credit_entry"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "user"])]

    def __str__(self) -> str:
        sinal = "+" if self.amount >= 0 else ""
        return f"{sinal}{self.amount} {self.get_reason_display()}"
