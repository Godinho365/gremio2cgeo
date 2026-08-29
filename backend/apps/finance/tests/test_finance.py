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


def test_cancel_payment_reopens_every_due_it_settled(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro8", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, due_day=10, started_period=_period(0))
        paid_at = _dt(0)
        settled = FinanceService().register_payment(
            user=user, amount=Decimal("300.00"), method="dinheiro", paid_at=paid_at,
        )
        one_of_them = settled[1].id
        reopened = FinanceService().cancel_payment(due_id=one_of_them)
        reopened_periods = sorted(d.period for d in reopened)
    assert reopened_periods == [_period(0), _period(1), _period(2)]
    assert all(d.status != DueStatus.PAID for d in reopened)
    assert all(d.settled_by_id is None for d in reopened)


def test_cancel_payment_reverses_the_overpayment_credit(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro9", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, due_day=10, started_period=_period(0)
        )
        paid_at = _dt(0)
        settled = FinanceService().register_payment(
            user=user, amount=Decimal("150.00"), method="dinheiro", paid_at=paid_at,
        )
        FinanceService().cancel_payment(due_id=settled[0].id)
        balance = FinanceCredit.objects.filter(billing_profile=profile).aggregate(
            s=Sum("amount")
        )["s"]
    assert balance == Decimal("0.00")


def test_cancel_payment_on_unpaid_due_is_rejected(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro10", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, due_day=10, started_period=_period(0))
        unpaid = Due.objects.filter(billing_profile__user=user).first()
        with pytest.raises(BusinessRuleError):
            FinanceService().cancel_payment(due_id=unpaid.id)


def test_roll_all_recomputes_status_by_date(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro11", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, due_day=10, started_period=_period(-2))
        FinanceService().roll_all()
        first_due = Due.objects.filter(billing_profile__user=user).order_by("period").first()
    # Início 2 meses atrás: o primeiro período está bem além dos 15 dias de tolerância.
    assert first_due.status == DueStatus.DELINQUENT


def test_roll_all_deactivates_billing_for_soldado_or_cabo(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro12", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, due_day=10, started_period=_period(0)
        )
        user.posto_graduacao = "Sd"
        user.save(update_fields=["posto_graduacao"])
        FinanceService().roll_all()
        profile.refresh_from_db()
    assert profile.is_active is False


def test_roll_all_consumes_accumulated_credit(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro13", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, due_day=10, started_period=_period(0)
        )
        paid_at = _dt(0)
        # Dois pagamentos de resto que juntos fecham uma mensalidade inteira.
        FinanceService().register_payment(
            user=user, amount=Decimal("60.00"), method="dinheiro", paid_at=paid_at
        )
        FinanceService().register_payment(
            user=user, amount=Decimal("40.00"), method="dinheiro", paid_at=paid_at
        )
        FinanceService().roll_all()
        paid_count = Due.objects.filter(
            billing_profile=profile, status=DueStatus.PAID
        ).count()
    assert paid_count == 1


def test_roll_dues_task_runs_for_all_tenants(tenant_a, tenant_b):
    from apps.finance.tasks import roll_dues

    with use_tenant(tenant_a.id):
        user_a = UserService().create_user(
            username="membroA", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user_a, due_day=10, started_period=_period(0))
    with use_tenant(tenant_b.id):
        user_b = UserService().create_user(
            username="membroB", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_b.id,
        )
        FinanceService().activate_billing(user=user_b, due_day=10, started_period=_period(0))

    processed = roll_dues()
    assert processed == 2


def test_summary_for_reports_the_fields_from_the_spec(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro14", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, due_day=10, started_period=_period(0)
        )
        paid_at = _dt(0)
        FinanceService().register_payment(
            user=user, amount=Decimal("200.00"), method="dinheiro", paid_at=paid_at
        )
        # register_payment busca o profile de novo internamente e atualiza
        # essa instância — a variável local `profile` (retornada por
        # activate_billing, antes do pagamento) ficou obsoleta.
        profile.refresh_from_db()
        summary = FinanceService().summary_for(profile)
    assert summary["months_paid"] == 2
    # register_payment (Task 4) mantém WINDOW_MONTHS_AHEAD (2) mensalidades
    # abertas à frente do que acabou de ser pago — não apenas 1 (ver comentário
    # em FinanceService.register_payment / _extend_until).
    assert summary["months_open"] == 2
    assert summary["paid_through_period"] == _period(1)
    assert summary["pending_amount"] == Decimal("200.00")
    assert summary["last_payment_at"] == paid_at


def test_dashboard_counts_active_profiles_by_financial_status(tenant_a):
    with use_tenant(tenant_a.id):
        em_dia = UserService().create_user(
            username="membro15", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        atrasado = UserService().create_user(
            username="membro16", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=em_dia, due_day=10, started_period=_period(0))
        FinanceService().activate_billing(
            user=atrasado, due_day=10, started_period=_period(-2)
        )
        FinanceService().roll_all()
        data = FinanceService().dashboard()
    assert data["total_users"] == 2
    assert data["overdue_count"] + data["delinquent_count"] >= 1


def test_activate_billing_via_api_requires_admin(client: APIClient):
    tenant, admin = _org("finapi1")
    with use_tenant(tenant.id):
        member = UserService().create_user(
            username="membro_api1", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
        plain = UserService().create_user(
            username="plain_fin1", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(plain)
    resp = client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )
    assert resp.status_code == 422, resp.data

    client.force_authenticate(admin)
    resp = client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["due_day"] == 10


def test_list_billing_profiles_requires_staff_read(client: APIClient):
    tenant, admin = _org("finapi2")
    with use_tenant(tenant.id):
        member = UserService().create_user(
            username="membro_api2", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
        plain = UserService().create_user(
            username="plain_fin2", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(plain)
    assert client.get("/api/billing-profiles").status_code == 422

    client.force_authenticate(admin)
    assert client.get("/api/billing-profiles").status_code == 200


def test_deactivate_billing_via_api(client: APIClient):
    tenant, admin = _org("finapi3")
    with use_tenant(tenant.id):
        member = UserService().create_user(
            username="membro_api3", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    created = client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )
    resp = client.post(f"/api/billing-profiles/{created.data['id']}/desativar")
    assert resp.status_code == 200, resp.data
    assert resp.data["is_active"] is False
