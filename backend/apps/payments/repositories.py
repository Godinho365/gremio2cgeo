from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils import timezone

from core.repositories import BaseRepository

from .models import OPEN_PAYMENT_STATUSES, CreditEntry, Payment


class PaymentRepository(BaseRepository[Payment]):
    model = Payment

    def overdue(self) -> models.QuerySet[Payment]:
        """Cobranças que passaram do prazo e ninguém pagou."""
        return self.query().filter(
            status__in=OPEN_PAYMENT_STATUSES, expires_at__lt=timezone.now()
        )

    def by_provider_id(self, provider_payment_id: str) -> Payment | None:
        """Busca sem escopo de tenant — de propósito.

        O webhook do provedor chega sem autenticação e sem saber de qual
        organização é a cobrança; o id externo é justamente o que amarra os
        dois. Quem chama isto precisa entrar no tenant do resultado antes de
        tocar em qualquer outro dado (ver PaymentService.apply_provider_status).
        """
        return Payment.objects.filter(provider_payment_id=provider_payment_id).first()


class CreditRepository(BaseRepository[CreditEntry]):
    model = CreditEntry

    def for_user(self, user_id) -> models.QuerySet[CreditEntry]:
        return self.query().filter(user_id=user_id)

    def balance(self, user_id) -> Decimal:
        total = self.for_user(user_id).aggregate(s=models.Sum("amount"))["s"]
        return total or Decimal("0.00")
