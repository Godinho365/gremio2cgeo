"""FinanceService — mensalidades: geração, alocação de pagamento, status.

Ver docs/superpowers/specs/2026-08-29-modulo-financeiro-fase1-design.md.
"""
from __future__ import annotations

import calendar
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import BARBERSHOP_ONLY_RANKS, User
from apps.payments.repositories import PaymentRepository
from core import audit
from core.exceptions import BusinessRuleError
from core.services import BaseService

from .models import BillingProfile, Due, DueStatus, FinancialStatus, membership_fee
from .repositories import DueRepository, FinanceRepository


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
    ) -> None:
        self.profiles = profiles or FinanceRepository()
        self.dues = dues or DueRepository()
        self.payments = payments or PaymentRepository()

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
