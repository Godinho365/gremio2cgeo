"""FinanceService — mensalidades: geração, alocação de pagamento, status.

Ver docs/superpowers/specs/2026-08-29-modulo-financeiro-fase1-design.md.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.payments.models import PaymentStatus
from apps.payments.repositories import PaymentRepository
from core import audit
from core.exceptions import BusinessRuleError
from core.services import BaseService

from .models import (
    OPEN_DUE_STATUSES,
    AssociadoInvite,
    BillingProfile,
    Due,
    DueStatus,
    FinanceCreditReason,
    FinancialStatus,
    PlanCode,
    eligible_plans_for,
    plan_price,
)
from .repositories import (
    AssociadoInviteRepository,
    DueRepository,
    FinanceCreditRepository,
    FinanceRepository,
)


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
        invites: AssociadoInviteRepository | None = None,
    ) -> None:
        self.profiles = profiles or FinanceRepository()
        self.dues = dues or DueRepository()
        self.payments = payments or PaymentRepository()
        self.invites = invites or AssociadoInviteRepository()
        self.credits = credits or FinanceCreditRepository()

    def _assert_eligible(self, user: User, plan: str) -> None:
        if plan not in eligible_plans_for(user.posto_graduacao):
            raise BusinessRuleError(
                f"Posto {user.posto_graduacao or '(não informado)'} não é elegível "
                "para este plano.",
                code="ineligible_rank",
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
            amount=plan_price(profile.plan),
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
        plan: str,
        due_day: int,
        started_period: date,
        actor_id: str | None = None,
    ) -> BillingProfile:
        self._assert_eligible(user, plan)
        if not (1 <= due_day <= 31):
            raise BusinessRuleError(
                "Dia de vencimento deve ser entre 1 e 31.", code="invalid_due_day"
            )
        started_period = _first_of_month(started_period)
        existing = self.profiles.profile_for_user(user.pk)
        if existing is not None:
            if existing.is_active:
                raise BusinessRuleError(
                    "Usuário já está na relação financeira.", code="already_active"
                )
            existing.is_active = True
            existing.plan = plan
            existing.due_day = due_day
            existing.save(update_fields=["is_active", "plan", "due_day", "updated_at"])
            self._ensure_window(existing)
            existing.financial_status = self._compute_financial_status(existing)
            existing.save(update_fields=["financial_status", "updated_at"])
            audit.record(
                action="finance.billing_reactivated",
                entity_type="BillingProfile",
                entity_id=existing.id,
                actor_id=actor_id,
                diff={"plan": plan, "due_day": due_day},
            )
            return existing

        oldest_allowed = _add_months(_first_of_month(timezone.localdate()), -60)
        if started_period < oldest_allowed:
            raise BusinessRuleError(
                "Mês de início não pode ser mais de 60 meses no passado.",
                code="started_period_too_old",
            )
        profile = self.profiles.create(
            user_id=user.pk, plan=plan, due_day=due_day, started_period=started_period
        )
        self._ensure_window(profile)
        profile.financial_status = self._compute_financial_status(profile)
        profile.save(update_fields=["financial_status", "updated_at"])
        audit.record(
            action="finance.billing_activated",
            entity_type="BillingProfile",
            entity_id=profile.id,
            actor_id=actor_id,
            diff={"plan": plan, "due_day": due_day, "started_period": str(profile.started_period)},
        )
        return profile

    def generate_associado_invite(
        self, *, user: User, actor_id: str | None = None
    ) -> AssociadoInvite:
        if PlanCode.ASSOCIADO not in eligible_plans_for(user.posto_graduacao):
            raise BusinessRuleError(
                "Este posto não é elegível para o Associado.", code="ineligible_rank"
            )
        existing = self.profiles.profile_for_user(user.pk)
        if existing is not None and existing.is_active:
            raise BusinessRuleError(
                "Usuário já está na relação financeira.", code="already_active"
            )
        invite = self.invites.create(user_id=user.pk)
        audit.record(
            action="finance.associado_invite_generated",
            entity_type="AssociadoInvite",
            entity_id=invite.id,
            actor_id=actor_id,
        )
        return invite

    def list_pending_associado_invites(self):
        return self.invites.pending()

    @transaction.atomic
    def accept_associado_invite(self, *, token: str, actor: User) -> BillingProfile:
        invite = self.invites.get_by_token(token)
        if invite is None:
            raise BusinessRuleError("Convite não encontrado.", code="invite_not_found")
        if invite.user_id != actor.pk:
            raise BusinessRuleError("Este convite não é seu.", code="forbidden")
        if invite.used_at is not None:
            raise BusinessRuleError("Este convite já foi usado.", code="invite_already_used")
        if timezone.now() > invite.expires_at:
            raise BusinessRuleError("Este convite expirou.", code="invite_expired")

        today = timezone.localdate()
        profile = self.activate_billing(
            user=actor,
            plan=PlanCode.ASSOCIADO,
            due_day=today.day,
            started_period=_first_of_month(today),
            actor_id=str(actor.pk),
        )
        invite.used_at = timezone.now()
        invite.save(update_fields=["used_at", "updated_at"])
        audit.record(
            action="finance.associado_invite_accepted",
            entity_type="AssociadoInvite",
            entity_id=invite.id,
            actor_id=str(actor.pk),
        )
        return profile

    def _extend_until(self, profile: BillingProfile, min_open: int, today: date) -> None:
        current_open = self.dues.open_for_profile(profile).count()
        if current_open >= min_open:
            return
        latest = self.dues.latest_period(profile)
        period = _add_months(latest, 1) if latest else profile.started_period
        for _ in range(min_open - current_open):
            self._create_due(profile, period, today)
            period = _add_months(period, 1)

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

        fee = plan_price(profile.plan)
        periods_covered = int(amount // fee)
        remainder = amount - (periods_covered * fee)
        if periods_covered > 60:
            raise BusinessRuleError(
                "Pagamento cobre mais de 60 meses — verifique o valor informado.",
                code="too_many_periods",
            )

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

        settled += self._consume_credit(profile, paid_at.date())

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

    def _consume_credit(self, profile: BillingProfile, today: date) -> list[Due]:
        consumed: list[Due] = []
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
            consumed.append(due)
        return consumed

    def roll_all(self) -> int:
        """Reconciliação diária: janela, status por data, crédito acumulado."""
        today = timezone.localdate()
        processed = 0
        for profile in self.profiles.active_profiles():
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

    def summary_for(self, profile: BillingProfile) -> dict:
        today = timezone.localdate()
        all_dues = list(self.dues.for_profile(profile).order_by("period"))
        paid = [d for d in all_dues if d.status == DueStatus.PAID]
        open_dues = [d for d in all_dues if d.status in OPEN_DUE_STATUSES]
        next_due = open_dues[0] if open_dues else None
        return {
            "financial_status": profile.financial_status,
            "plan": profile.plan,
            "plan_label": profile.get_plan_display(),
            "due_day": profile.due_day,
            "next_due_date": next_due.due_date if next_due else None,
            "days_until_due": (next_due.due_date - today).days if next_due else None,
            "days_overdue": max(0, (today - next_due.due_date).days) if next_due else 0,
            "months_paid": len(paid),
            "months_paid_in_advance": sum(1 for d in paid if d.paid_in_advance),
            "months_open": len(open_dues),
            "pending_amount": sum((d.amount for d in open_dues), Decimal("0.00")),
            "last_payment_at": profile.last_payment_at,
            "paid_through_period": paid[-1].period if paid else None,
        }

    def dashboard(self, *, date_from: date | None = None, date_to: date | None = None) -> dict:
        today = timezone.localdate()
        profiles = list(self.profiles.active_profiles())
        by_status = {s.value: 0 for s in FinancialStatus}
        for profile in profiles:
            by_status[profile.financial_status] += 1

        soon_cutoff = today + timedelta(days=30)
        upcoming = self.dues.query().filter(
            billing_profile__is_active=True,
            status__in=(DueStatus.PENDING, DueStatus.DUE_SOON, DueStatus.DUE_TODAY),
            due_date__lte=soon_cutoff,
        )
        overdue = self.dues.query().filter(
            billing_profile__is_active=True, status__in=(DueStatus.OVERDUE, DueStatus.DELINQUENT)
        )
        pending = self.dues.query().filter(
            billing_profile__is_active=True, status__in=OPEN_DUE_STATUSES
        )

        finance_payment_ids = (
            self.dues.query()
            .filter(settled_by__isnull=False)
            .values_list("settled_by_id", flat=True)
            .distinct()
        )
        payments_qs = self.payments.query().filter(
            status=PaymentStatus.APPROVED, id__in=finance_payment_ids
        )
        if date_from:
            payments_qs = payments_qs.filter(paid_at__date__gte=date_from)
        if date_to:
            payments_qs = payments_qs.filter(paid_at__date__lte=date_to)
        received = payments_qs.aggregate(s=Sum("amount"))["s"] or Decimal("0.00")

        advance_credit = self.credits.query().filter(
            billing_profile__is_active=True
        ).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")

        return {
            "total_users": len(profiles),
            "up_to_date_count": by_status[FinancialStatus.UP_TO_DATE],
            "paid_in_advance_count": by_status[FinancialStatus.PAID_IN_ADVANCE],
            "due_soon_count": by_status[FinancialStatus.DUE_SOON],
            "due_today_count": by_status[FinancialStatus.DUE_TODAY],
            "overdue_count": by_status[FinancialStatus.OVERDUE],
            "delinquent_count": by_status[FinancialStatus.DELINQUENT],
            "dues_upcoming_30_days": upcoming.count(),
            "dues_overdue": overdue.count(),
            "payments_received": received,
            "pending_amount": pending.aggregate(s=Sum("amount"))["s"] or Decimal("0.00"),
            "advance_payments_received": advance_credit,
            "upcoming_receivable": upcoming.aggregate(s=Sum("amount"))["s"] or Decimal("0.00"),
        }
