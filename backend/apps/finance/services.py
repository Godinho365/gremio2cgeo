"""FinanceService — mensalidades: geração, alocação de pagamento, status.

Ver docs/superpowers/specs/2026-08-29-modulo-financeiro-fase1-design.md.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import BARBERSHOP_ONLY_RANKS, User
from apps.payments.models import PaymentStatus
from apps.payments.repositories import PaymentRepository
from core import audit
from core.exceptions import BusinessRuleError
from core.services import BaseService

from .models import (
    BillingProfile,
    Due,
    DueStatus,
    FinanceCreditReason,
    FinancialStatus,
    membership_fee,
)
from .repositories import DueRepository, FinanceCreditRepository, FinanceRepository


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, n: int) -> date:
    month_index = d.month - 1 + n
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _due_date_for(period: date, due_day: int) -> date:
    last_day = calendar.monthrange(period.year, period.month)[1]
    return period.replace(day=min(due_day, last_day))


class FinanceService(BaseService):
    WINDOW_MONTHS_AHEAD = 2
    DUE_SOON_DAYS = 5
    DELINQUENT_AFTER_DAYS = 15

    def __init__(
        self,
        profiles: FinanceRepository | None = None,
        dues: DueRepository | None = None,
        payments: PaymentRepository | None = None,
        credits: FinanceCreditRepository | None = None,
    ) -> None:
        self.profiles = profiles or FinanceRepository()
        self.dues = dues or DueRepository()
        self.payments = payments or PaymentRepository()
        self.credits = credits or FinanceCreditRepository()

    def _refuse_if_ineligible(self, user: User) -> None:
        if user.posto_graduacao in BARBERSHOP_ONLY_RANKS:
            raise BusinessRuleError(
                "Praças (Sd/Cb) não entram na relação financeira.", code="ineligible_rank"
            )

    def _status_for(self, due_date: date, today: date) -> str:
        days_late = (today - due_date).days
        if days_late > self.DELINQUENT_AFTER_DAYS:
            return DueStatus.DELINQUENT
        if days_late > 0:
            return DueStatus.OVERDUE
        if days_late == 0:
            return DueStatus.DUE_TODAY
        if days_late >= -self.DUE_SOON_DAYS:
            return DueStatus.DUE_SOON
        return DueStatus.PENDING

    def _create_due(self, profile: BillingProfile, period: date, today: date) -> Due:
        due_date = _due_date_for(period, profile.due_day)
        return self.dues.create(
            billing_profile=profile,
            period=period,
            due_date=due_date,
            amount=membership_fee(),
            status=self._status_for(due_date, today),
        )

    def _ensure_window(self, profile: BillingProfile, *, today: date | None = None) -> None:
        today = today or timezone.localdate()
        target = _add_months(_first_of_month(today), self.WINDOW_MONTHS_AHEAD)
        latest = self.dues.latest_period(profile)
        period = _add_months(latest, 1) if latest else profile.started_period
        while period <= target:
            self._create_due(profile, period, today)
            period = _add_months(period, 1)

    def _compute_financial_status(
        self, profile: BillingProfile, *, today: date | None = None
    ) -> str:
        today = today or timezone.localdate()
        open_dues = list(self.dues.open_for_profile(profile))
        precedence = (
            (DueStatus.DELINQUENT, FinancialStatus.DELINQUENT),
            (DueStatus.OVERDUE, FinancialStatus.OVERDUE),
            (DueStatus.DUE_TODAY, FinancialStatus.DUE_TODAY),
            (DueStatus.DUE_SOON, FinancialStatus.DUE_SOON),
        )
        for due_status, financial_status in precedence:
            if any(d.status == due_status for d in open_dues):
                return financial_status
        latest_paid = (
            self.dues.for_profile(profile)
            .filter(status=DueStatus.PAID)
            .order_by("-period")
            .first()
        )
        if latest_paid and latest_paid.period > _first_of_month(today):
            return FinancialStatus.PAID_IN_ADVANCE
        return FinancialStatus.UP_TO_DATE

    @transaction.atomic
    def activate_billing(
        self,
        *,
        user: User,
        due_day: int,
        started_period: date,
        actor_id: str | None = None,
    ) -> BillingProfile:
        self._refuse_if_ineligible(user)
        if not (1 <= due_day <= 31):
            raise BusinessRuleError(
                "Dia de vencimento deve ser entre 1 e 31.", code="invalid_due_day"
            )
        if self.profiles.profile_for_user(user.pk) is not None:
            raise BusinessRuleError(
                "Usuário já está na relação financeira.", code="already_active"
            )
        profile = self.profiles.create(
            user_id=user.pk, due_day=due_day, started_period=_first_of_month(started_period)
        )
        self._ensure_window(profile)
        profile.financial_status = self._compute_financial_status(profile)
        profile.save(update_fields=["financial_status", "updated_at"])
        audit.record(
            action="finance.billing_activated",
            entity_type="BillingProfile",
            entity_id=profile.id,
            actor_id=actor_id,
            diff={"due_day": due_day, "started_period": str(profile.started_period)},
        )
        return profile

    def _extend_until(self, profile: BillingProfile, min_open: int, today: date) -> None:
        while self.dues.open_for_profile(profile).count() < min_open:
            latest = self.dues.latest_period(profile)
            period = _add_months(latest, 1) if latest else profile.started_period
            self._create_due(profile, period, today)

    @transaction.atomic
    def register_payment(
        self,
        *,
        user: User,
        amount: Decimal,
        method: str,
        paid_at: datetime,
        actor_id: str | None = None,
    ) -> list[Due]:
        amount = Decimal(str(amount))
        if amount <= 0:
            raise BusinessRuleError(
                "Valor do pagamento deve ser maior que zero.", code="invalid_amount"
            )
        profile = self.profiles.profile_for_user(user.pk)
        if profile is None or not profile.is_active:
            raise BusinessRuleError(
                "Usuário não está na relação financeira.", code="not_in_billing"
            )

        fee = membership_fee()
        periods_covered = int(amount // fee)
        remainder = amount - (periods_covered * fee)

        payment = self.payments.create(
            provider="",
            method=method,
            amount=amount,
            status=PaymentStatus.APPROVED,
            payer_id=user.pk,
            paid_at=paid_at,
            description="Mensalidade",
            created_by_id=actor_id,
        )

        settled: list[Due] = []
        if periods_covered > 0:
            # Além dos `periods_covered` a liquidar, mantém o mesmo colchão de
            # WINDOW_MONTHS_AHEAD sempre visível à frente do que acabou de ser
            # pago — o mesmo invariante de janela que `_ensure_window` mantém
            # a partir de hoje, agora reancorado na nova fronteira paga (senão
            # um pagamento que cobre mais meses do que os já gerados deixaria
            # a pessoa sem nenhuma mensalidade pendente visível).
            self._extend_until(
                profile, periods_covered + self.WINDOW_MONTHS_AHEAD, today=paid_at.date()
            )
            open_dues = list(self.dues.open_for_profile(profile)[:periods_covered])
            current_period = _first_of_month(paid_at.date())
            for due in open_dues:
                due.status = DueStatus.PAID
                due.paid_in_advance = due.period > current_period
                due.settled_by = payment
                due.paid_at = paid_at
                due.save(
                    update_fields=[
                        "status", "paid_in_advance", "settled_by", "paid_at", "updated_at"
                    ]
                )
                settled.append(due)

        if remainder > 0:
            self.credits.create(
                billing_profile=profile,
                amount=remainder,
                reason=FinanceCreditReason.OVERPAYMENT,
                payment=payment,
            )

        profile.last_payment_at = paid_at
        profile.financial_status = self._compute_financial_status(profile)
        profile.save(update_fields=["last_payment_at", "financial_status", "updated_at"])

        audit.record(
            action="finance.payment_registered",
            entity_type="BillingProfile",
            entity_id=profile.id,
            actor_id=actor_id,
            diff={"amount": str(amount), "method": method, "periods": periods_covered},
        )
        return settled

    @transaction.atomic
    def cancel_payment(self, *, due_id: str, actor_id: str | None = None) -> list[Due]:
        due = self.dues.get(due_id)
        if due.settled_by_id is None:
            raise BusinessRuleError("Esta mensalidade não está paga.", code="not_paid")
        payment = due.settled_by
        reopened = list(
            self.dues.query()
            .filter(settled_by=payment)
            .select_related("billing_profile")
        )
        today = timezone.localdate()
        for reopened_due in reopened:
            reopened_due.status = self._status_for(reopened_due.due_date, today)
            reopened_due.paid_in_advance = False
            reopened_due.settled_by = None
            reopened_due.paid_at = None
            reopened_due.save(
                update_fields=[
                    "status", "paid_in_advance", "settled_by", "paid_at", "updated_at"
                ]
            )

        payment.status = PaymentStatus.CANCELLED
        payment.save(update_fields=["status", "updated_at"])

        for credit in self.credits.for_payment(payment).filter(
            reason=FinanceCreditReason.OVERPAYMENT
        ):
            self.credits.create(
                billing_profile=credit.billing_profile,
                amount=-credit.amount,
                reason=FinanceCreditReason.REVERSED,
                payment=payment,
                note="Estorno de pagamento cancelado",
            )

        profile = reopened[0].billing_profile if reopened else due.billing_profile
        profile.financial_status = self._compute_financial_status(profile, today=today)
        profile.save(update_fields=["financial_status", "updated_at"])

        audit.record(
            action="finance.payment_cancelled",
            entity_type="Payment",
            entity_id=payment.id,
            actor_id=actor_id,
        )
        return reopened

    @transaction.atomic
    def deactivate_billing(
        self, *, profile: BillingProfile, actor_id: str | None = None
    ) -> BillingProfile:
        profile.is_active = False
        profile.save(update_fields=["is_active", "updated_at"])
        audit.record(
            action="finance.billing_deactivated",
            entity_type="BillingProfile",
            entity_id=profile.id,
            actor_id=actor_id,
        )
        return profile

    @transaction.atomic
    def update_due_day(
        self, *, profile: BillingProfile, due_day: int, actor_id: str | None = None
    ) -> BillingProfile:
        if not (1 <= due_day <= 31):
            raise BusinessRuleError(
                "Dia de vencimento deve ser entre 1 e 31.", code="invalid_due_day"
            )
        profile.due_day = due_day
        profile.save(update_fields=["due_day", "updated_at"])
        today = timezone.localdate()
        for due in self.dues.open_for_profile(profile):
            due.due_date = _due_date_for(due.period, due_day)
            due.status = self._status_for(due.due_date, today)
            due.save(update_fields=["due_date", "status", "updated_at"])
        profile.financial_status = self._compute_financial_status(profile, today=today)
        profile.save(update_fields=["financial_status", "updated_at"])
        audit.record(
            action="finance.due_day_updated",
            entity_type="BillingProfile",
            entity_id=profile.id,
            actor_id=actor_id,
            diff={"due_day": due_day},
        )
        return profile

    def _credit_balance(self, profile: BillingProfile) -> Decimal:
        return self.credits.balance(profile)

    def _consume_credit(self, profile: BillingProfile, today: date) -> None:
        balance = self._credit_balance(profile)
        for due in self.dues.open_for_profile(profile):
            if balance < due.amount:
                break
            due.status = DueStatus.PAID
            due.paid_in_advance = due.period > _first_of_month(today)
            due.paid_at = timezone.now()
            due.save(update_fields=["status", "paid_in_advance", "paid_at", "updated_at"])
            self.credits.create(
                billing_profile=profile,
                amount=-due.amount,
                reason=FinanceCreditReason.CONSUMED,
                due=due,
            )
            balance -= due.amount

    def roll_all(self) -> int:
        """Reconciliação diária: janela, status por data, Sd/Cb, crédito acumulado."""
        today = timezone.localdate()
        processed = 0
        for profile in self.profiles.active_profiles():
            if profile.user.posto_graduacao in BARBERSHOP_ONLY_RANKS:
                self.deactivate_billing(profile=profile)
                continue
            self._ensure_window(profile, today=today)
            for due in self.dues.open_for_profile(profile):
                new_status = self._status_for(due.due_date, today)
                if new_status != due.status:
                    due.status = new_status
                    due.save(update_fields=["status", "updated_at"])
            self._consume_credit(profile, today)
            profile.financial_status = self._compute_financial_status(profile, today=today)
            profile.save(update_fields=["financial_status", "updated_at"])
            processed += 1
        return processed
