"""Módulo Financeiro (Fase 1): mensalidades, alocação de pagamento, status."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.db.models import Sum
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import RoleCode
from apps.accounts.services import OnboardingService, UserService
from apps.finance.models import (
    BillingProfile,
    Due,
    DueStatus,
    FinanceCredit,
    FinancialStatus,
)
from apps.finance.services import FinanceService
from core.context import use_tenant
from core.exceptions import BusinessRuleError

pytestmark = pytest.mark.django_db


def _org(name: str):
    return OnboardingService().create_organization(
        org_name=name, admin_username=f"admin_{name}", admin_password="supersecret123"
    )


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture(autouse=True)
def _fee_configurada(settings):
    """Trava o valor da mensalidade nos testes — independe do .env local
    (mesmo motivo do `pix_configurado` autouse em apps/barbershop/tests/conftest.py:
    testes não podem depender do que alguém deixou configurado na máquina)."""
    settings.MEMBERSHIP_FEE = "100.00"


# Testes de mensalidade não podem cravar datas de calendário absolutas (ex.:
# "2026-08-01") — a suíte ficaria correta só até o mês virar. Tudo aqui é
# relativo ao mês corrente de verdade (`timezone.localdate()`), igual ao
# padrão já usado em apps/scheduling/tests (`_dt(day, hour)`).
def _period(offset_months: int) -> date:
    """1º dia do mês, deslocado `offset_months` a partir do mês corrente."""
    base = timezone.localdate().replace(day=1)
    month_index = base.month - 1 + offset_months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _period_str(offset_months: int) -> str:
    return _period(offset_months).isoformat()


def _dt(offset_months: int, day: int = 5, hour: int = 10):
    """Datetime aware dentro do período de `offset_months`, dia fixo (nunca cai fora do mês)."""
    period = _period(offset_months)
    return timezone.make_aware(datetime(period.year, period.month, day, hour, 0))


def _dt_str(offset_months: int, day: int = 5, hour: int = 10) -> str:
    return _dt(offset_months, day, hour).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_billing_profile_and_due_models_exist(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro1", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        profile = BillingProfile.objects.create(
            tenant_id=tenant_a.id, user=user, due_day=10, started_period=_period(0),
        )
        due = Due.objects.create(
            tenant_id=tenant_a.id, billing_profile=profile, period=_period(0),
            due_date=_period(0).replace(day=10), amount=Decimal("100.00"), status=DueStatus.PENDING,
        )
    assert profile.financial_status == FinancialStatus.UP_TO_DATE
    assert due.billing_profile_id == profile.id


def test_due_date_respects_short_months():
    from apps.finance.services import _due_date_for

    assert _due_date_for(date(2026, 2, 1), 31) == date(2026, 2, 28)
    assert _due_date_for(date(2026, 8, 1), 31) == date(2026, 8, 31)
    assert _due_date_for(date(2026, 8, 1), 10) == date(2026, 8, 10)


def test_activate_billing_generates_current_and_two_months_ahead(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro2", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, due_day=10, started_period=_period(0),
        )
        periods = list(
            Due.objects.filter(billing_profile=profile).order_by("period").values_list(
                "period", flat=True
            )
        )
    assert periods == [_period(0), _period(1), _period(2)]


def test_activate_billing_refuses_soldado_or_cabo(tenant_a):
    with use_tenant(tenant_a.id):
        soldado = UserService().create_user(
            username="soldado_fin", password="supersecret123",
            posto_graduacao="Sd", tenant_id=tenant_a.id,
        )
        with pytest.raises(BusinessRuleError):
            FinanceService().activate_billing(
                user=soldado, due_day=10, started_period=_period(0)
            )


def test_activate_billing_twice_is_rejected(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro3", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, due_day=10, started_period=_period(0))
        with pytest.raises(BusinessRuleError):
            FinanceService().activate_billing(
                user=user, due_day=15, started_period=_period(0)
            )


def test_register_payment_allocates_across_periods_advance_example(tenant_a):
    """R$100/mês, pagamento de R$500 → 5 meses pagos, o 6º pendente (exemplo do spec)."""
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro4", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, due_day=10, started_period=_period(0))
        paid_at = _dt(0)
        settled = FinanceService().register_payment(
            user=user, amount=Decimal("500.00"), method="dinheiro", paid_at=paid_at,
        )
        settled_periods = [d.period for d in settled]
        profile = BillingProfile.objects.get(user=user)
        all_dues = {d.period: d.status for d in Due.objects.filter(billing_profile=profile)}
    assert settled_periods == [_period(0), _period(1), _period(2), _period(3), _period(4)]
    assert all_dues[_period(5)] == DueStatus.PENDING
    # O mês 0 era o mês corrente no pagamento → não é "antecipado"; o mês 4 é.
    assert settled[0].paid_in_advance is False
    assert settled[-1].paid_in_advance is True


def test_register_payment_extends_window_beyond_two_months(tenant_a):
    """6 meses pagos de uma vez, mas só 3 (atual+2) tinham sido gerados."""
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro5", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, due_day=10, started_period=_period(0))
        paid_at = _dt(0)
        settled = FinanceService().register_payment(
            user=user, amount=Decimal("600.00"), method="dinheiro", paid_at=paid_at,
        )
    assert len(settled) == 6
    assert settled[-1].period == _period(5)


def test_register_payment_remainder_becomes_credit(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro6", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, due_day=10, started_period=_period(0)
        )
        paid_at = _dt(0)
        settled = FinanceService().register_payment(
            user=user, amount=Decimal("150.00"), method="dinheiro", paid_at=paid_at,
        )
        credit_balance = FinanceCredit.objects.filter(billing_profile=profile).aggregate(
            s=Sum("amount")
        )["s"]
    assert len(settled) == 1
    assert credit_balance == Decimal("50.00")


def test_register_payment_rejects_zero_or_negative(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro7", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, due_day=10, started_period=_period(0))
        with pytest.raises(BusinessRuleError):
            FinanceService().register_payment(
                user=user, amount=Decimal("0"), method="dinheiro", paid_at=timezone.now()
            )
