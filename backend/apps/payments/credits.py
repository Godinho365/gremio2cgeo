"""CreditService — crédito do usuário (RN-P5, RN-P6).

RN-P5  Cancelar um horário já pago vira crédito no perfil, não estorno: o
       dinheiro fica no grêmio e a pessoa usa numa próxima vez.
RN-P6  Saldo nunca fica negativo; e cada movimentação tem uma linha no extrato.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.accounts.models import User
from core import audit
from core.exceptions import BusinessRuleError
from core.services import BaseService

from .models import CreditEntry, CreditReason, Payment
from .repositories import CreditRepository

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")


class CreditService(BaseService):
    def __init__(self, credits: CreditRepository | None = None) -> None:
        self.credits = credits or CreditRepository()

    def balance(self, user_id: UUID | str) -> Decimal:
        return self.credits.balance(user_id)

    def statement(self, user_id: UUID | str, limit: int = 50):
        return self.credits.for_user(user_id).select_related("payment")[:limit]

    def _lock_user(self, user_id: UUID | str) -> None:
        """Serializa as operações de crédito da pessoa.

        Sem a trava, dois pedidos ao mesmo tempo leem o mesmo saldo e gastam o
        crédito duas vezes. Travar a linha do usuário é o suficiente: todo
        lançamento passa por aqui.
        """
        User.objects.select_for_update().filter(pk=user_id).first()

    @transaction.atomic
    def add(
        self,
        *,
        user_id: UUID | str,
        amount: Decimal,
        reason: str,
        payment: Payment | None = None,
        note: str = "",
        actor_id: UUID | str | None = None,
    ) -> CreditEntry:
        if amount <= ZERO:
            raise BusinessRuleError("Crédito precisa ser maior que zero.", code="invalid_credit")
        self._lock_user(user_id)
        entry = self.credits.create(
            user_id=user_id,
            amount=amount,
            reason=reason,
            payment=payment,
            note=note,
            created_by_id=actor_id or user_id,
        )
        audit.record(
            action="credit.added",
            entity_type="CreditEntry",
            entity_id=entry.id,
            actor_id=actor_id or user_id,
            diff={"amount": str(amount), "reason": reason, "note": note},
        )
        return entry

    @transaction.atomic
    def spend(
        self,
        *,
        user_id: UUID | str,
        amount: Decimal,
        reason: str = CreditReason.USED_IN_APPOINTMENT,
        note: str = "",
        actor_id: UUID | str | None = None,
    ) -> CreditEntry:
        if amount <= ZERO:
            raise BusinessRuleError(
                "Valor a debitar precisa ser maior que zero.", code="invalid_debit"
            )
        self._lock_user(user_id)
        saldo = self.balance(user_id)
        if saldo < amount:  # RN-P6
            raise BusinessRuleError(
                f"Crédito insuficiente: você tem R$ {saldo} e o corte custa R$ {amount}.",
                code="insufficient_credit",
            )
        entry = self.credits.create(
            user_id=user_id,
            amount=-amount,
            reason=reason,
            note=note,
            created_by_id=actor_id or user_id,
        )
        audit.record(
            action="credit.spent",
            entity_type="CreditEntry",
            entity_id=entry.id,
            actor_id=actor_id or user_id,
            diff={"amount": str(amount), "note": note},
        )
        return entry

    def has_enough(self, *, user_id: UUID | str, amount: Decimal) -> bool:
        return self.balance(user_id) >= amount
