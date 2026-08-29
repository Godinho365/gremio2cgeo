from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import models

from core.repositories import BaseRepository

from .models import OPEN_DUE_STATUSES, BillingProfile, Due, FinanceCredit


class FinanceRepository(BaseRepository[BillingProfile]):
    model = BillingProfile

    def profile_for_user(self, user_id) -> BillingProfile | None:
        return self.query().filter(user_id=user_id).first()

    def active_profiles(self) -> models.QuerySet[BillingProfile]:
        return self.query().filter(is_active=True).select_related("user")


class DueRepository(BaseRepository[Due]):
    model = Due

    def for_profile(self, billing_profile: BillingProfile) -> models.QuerySet[Due]:
        return self.query().filter(billing_profile=billing_profile)

    def open_for_profile(self, billing_profile: BillingProfile) -> models.QuerySet[Due]:
        return self.for_profile(billing_profile).filter(status__in=OPEN_DUE_STATUSES).order_by(
            "period"
        )

    def latest_period(self, billing_profile: BillingProfile) -> date | None:
        last = self.for_profile(billing_profile).order_by("-period").first()
        return last.period if last else None


class FinanceCreditRepository(BaseRepository[FinanceCredit]):
    model = FinanceCredit

    def for_profile(self, billing_profile: BillingProfile) -> models.QuerySet[FinanceCredit]:
        return self.query().filter(billing_profile=billing_profile)

    def balance(self, billing_profile: BillingProfile) -> Decimal:
        total = self.for_profile(billing_profile).aggregate(s=models.Sum("amount"))["s"]
        return total or Decimal("0.00")
