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
    PlanCode,
    eligible_plans_for,
    plan_price,
)
from apps.finance.repositories import FinanceRepository
from apps.finance.services import FinanceService
from apps.payments.models import Payment, PaymentStatus
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
    """Trava o valor dos planos nos testes — independe do .env local
    (mesmo motivo do `pix_configurado` autouse em apps/barbershop/tests/conftest.py:
    testes não podem depender do que alguém deixou configurado na máquina).
    Os dois planos usam o mesmo valor de propósito: a maioria dos testes
    daqui não testa qual plano está ativo, só a mecânica de alocação de
    pagamento — travar os dois no mesmo número evita reescrever a aritmética
    de cada teste. `test_plan_price_reads_from_settings` cobre os valores
    reais (30/20) separadamente."""
    settings.ASSOCIADO_FEE = "100.00"
    settings.BARBEARIA_FEE = "100.00"


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
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        profile = BillingProfile.objects.create(
            tenant_id=tenant_a.id, user=user, plan=PlanCode.ASSOCIADO,
            due_day=10, started_period=_period(0),
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


def test_plan_price_reads_from_settings(settings):
    settings.ASSOCIADO_FEE = "30.00"
    settings.BARBEARIA_FEE = "20.00"
    assert plan_price(PlanCode.ASSOCIADO) == Decimal("30.00")
    assert plan_price(PlanCode.BARBEARIA) == Decimal("20.00")


@pytest.mark.parametrize(
    "posto,expected",
    [
        ("", frozenset()),
        ("Sd", frozenset()),
        ("Sd EV", frozenset({"barbearia"})),
        ("Sd EP", frozenset({"associado", "barbearia"})),
        ("Cb", frozenset({"associado", "barbearia"})),
        ("Cel", frozenset({"associado"})),
        ("ST", frozenset({"associado"})),
    ],
)
def test_eligible_plans_for_matches_the_matrix(posto, expected):
    assert eligible_plans_for(posto) == expected




def test_activate_billing_generates_current_and_two_months_ahead(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro2", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0),
        )
        periods = list(
            Due.objects.filter(billing_profile=profile).order_by("period").values_list(
                "period", flat=True
            )
        )
    assert periods == [_period(0), _period(1), _period(2)]


def test_activate_billing_refuses_plan_not_eligible_for_rank(tenant_a):
    with use_tenant(tenant_a.id):
        coronel = UserService().create_user(
            username="coronel_fin", password="supersecret123",
            posto_graduacao="Cel", tenant_id=tenant_a.id,
        )
        with pytest.raises(BusinessRuleError):
            FinanceService().activate_billing(
                user=coronel, plan=PlanCode.BARBEARIA, due_day=10, started_period=_period(0)
            )


def test_activate_billing_accepts_barbearia_plan_for_sd_ev(tenant_a):
    with use_tenant(tenant_a.id):
        soldado_ev = UserService().create_user(
            username="sdev_fin", password="supersecret123",
            posto_graduacao="Sd EV", tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=soldado_ev, plan=PlanCode.BARBEARIA, due_day=10, started_period=_period(0)
        )
    assert profile.plan == PlanCode.BARBEARIA


def test_activate_billing_refuses_unclassified_legacy_sd(tenant_a):
    with use_tenant(tenant_a.id):
        legado = UserService().create_user(
            username="sd_legado_fin", password="supersecret123",
            posto_graduacao="Sd", tenant_id=tenant_a.id,
        )
        with pytest.raises(BusinessRuleError):
            FinanceService().activate_billing(
                user=legado, plan=PlanCode.BARBEARIA, due_day=10, started_period=_period(0)
            )


def test_activate_billing_twice_is_rejected(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro3", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0))
        with pytest.raises(BusinessRuleError):
            FinanceService().activate_billing(
                user=user, plan=PlanCode.ASSOCIADO, due_day=15, started_period=_period(0)
            )


def test_register_payment_allocates_across_periods_advance_example(tenant_a):
    """R$100/mês, pagamento de R$500 → 5 meses pagos, o 6º pendente (exemplo do spec)."""
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro4", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0))
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
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0))
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
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0)
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
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0))
        with pytest.raises(BusinessRuleError):
            FinanceService().register_payment(
                user=user, amount=Decimal("0"), method="dinheiro", paid_at=timezone.now()
            )


def test_cancel_payment_reopens_every_due_it_settled(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro8", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0))
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
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0)
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
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0))
        unpaid = Due.objects.filter(billing_profile__user=user).first()
        with pytest.raises(BusinessRuleError):
            FinanceService().cancel_payment(due_id=unpaid.id)


def test_roll_all_recomputes_status_by_date(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro11", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(-2))
        FinanceService().roll_all()
        first_due = Due.objects.filter(billing_profile__user=user).order_by("period").first()
    # Início 2 meses atrás: o primeiro período está bem além dos 15 dias de tolerância.
    assert first_due.status == DueStatus.DELINQUENT


def test_roll_all_keeps_billing_active_for_praca_ranks(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="cb_roll", password="supersecret123",
            posto_graduacao="Cb", tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, plan=PlanCode.BARBEARIA, due_day=10, started_period=_period(0)
        )
        FinanceService().roll_all()
        profile.refresh_from_db()
    assert profile.is_active is True


def test_roll_all_consumes_accumulated_credit(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro13", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0)
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
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user_a, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0))
    with use_tenant(tenant_b.id):
        user_b = UserService().create_user(
            username="membroB", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_b.id,
        )
        FinanceService().activate_billing(user=user_b, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0))

    processed = roll_dues()
    assert processed == 2


def test_summary_for_reports_the_fields_from_the_spec(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro14", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0)
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
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        atrasado = UserService().create_user(
            username="membro16", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=em_dia, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0))
        FinanceService().activate_billing(
            user=atrasado, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(-2)
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
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
        plain = UserService().create_user(
            username="plain_fin1", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(plain)
    resp = client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "plan": "associado", "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )
    assert resp.status_code == 422, resp.data

    client.force_authenticate(admin)
    resp = client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "plan": "associado", "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["due_day"] == 10


def test_list_billing_profiles_requires_staff_read(client: APIClient):
    tenant, admin = _org("finapi2")
    with use_tenant(tenant.id):
        member = UserService().create_user(
            username="membro_api2", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
        plain = UserService().create_user(
            username="plain_fin2", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant.id,
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
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    created = client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "plan": "associado", "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )
    resp = client.post(f"/api/billing-profiles/{created.data['id']}/desativar")
    assert resp.status_code == 200, resp.data
    assert resp.data["is_active"] is False


def test_update_due_day_via_api_requires_admin(client: APIClient):
    """`_can_manage` (não `_can_read`) tem que barrar o PATCH — por isso o
    usuário rejeitado aqui é `DIRECTOR` (tem leitura financeira via
    `_READ_ROLES`, mas não é `ADMIN`), não um usuário sem papel nenhum: um
    `RoleCode.USER` puro já cairia em `get_object()` → `_can_read` antes de
    chegar no `_can_manage`, mascarando uma eventual regressão nesse guard
    específico."""
    tenant, admin = _org("finapi4")
    with use_tenant(tenant.id):
        member = UserService().create_user(
            username="membro_api4", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
        director = UserService().create_user(
            username="director_fin4", password="supersecret123",
            role_codes=[RoleCode.DIRECTOR], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    created = client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "plan": "associado", "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )
    profile_id = created.data["id"]

    client.force_authenticate(director)
    resp = client.patch(
        f"/api/billing-profiles/{profile_id}", {"due_day": 15}, format="json"
    )
    assert resp.status_code == 422, resp.data

    client.force_authenticate(admin)
    resp = client.patch(
        f"/api/billing-profiles/{profile_id}", {"due_day": 15}, format="json"
    )
    assert resp.status_code == 200, resp.data
    assert resp.data["due_day"] == 15


def test_registrar_pagamento_via_api(client: APIClient):
    tenant, admin = _org("finapi4")
    with use_tenant(tenant.id):
        member = UserService().create_user(
            username="membro_api4", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "plan": "associado", "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )
    resp = client.post(
        "/api/dues/registrar-pagamento",
        {
            "user": str(member.id),
            "amount": "200.00",
            "method": "dinheiro",
            "paid_at": _dt_str(0),
        },
        format="json",
    )
    assert resp.status_code == 200, resp.data
    assert len(resp.data) == 2


def test_registrar_pagamento_requires_admin(client: APIClient):
    """`_can_manage` (não `_can_read`) tem que barrar o POST — por isso o
    usuário rejeitado aqui é `DIRECTOR` (tem leitura financeira via
    `_READ_ROLES`, mas não é `ADMIN`), não um usuário sem papel financeiro
    nenhum: um `RoleCode.USER` puro poderia ser barrado por um guard
    diferente (ex.: leitura), mascarando uma eventual regressão no guard
    de `_can_manage` que este teste pretende cobrir (mesmo racional de
    `test_update_due_day_via_api_requires_admin`)."""
    tenant, admin = _org("finapi5")
    with use_tenant(tenant.id):
        member = UserService().create_user(
            username="membro_api5", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
        director = UserService().create_user(
            username="director_fin5", password="supersecret123",
            role_codes=[RoleCode.DIRECTOR], tenant_id=tenant.id,
        )
    client.force_authenticate(director)
    resp = client.post(
        "/api/dues/registrar-pagamento",
        {
            "user": str(member.id),
            "amount": "100.00",
            "method": "dinheiro",
            "paid_at": _dt_str(0),
        },
        format="json",
    )
    assert resp.status_code == 422


def test_cancelar_pagamento_via_api(client: APIClient):
    tenant, admin = _org("finapi6")
    with use_tenant(tenant.id):
        member = UserService().create_user(
            username="membro_api6", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "plan": "associado", "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )
    paid = client.post(
        "/api/dues/registrar-pagamento",
        {
            "user": str(member.id),
            "amount": "100.00",
            "method": "dinheiro",
            "paid_at": _dt_str(0),
        },
        format="json",
    )
    due_id = paid.data[0]["id"]
    resp = client.post(f"/api/dues/{due_id}/cancelar-pagamento")
    assert resp.status_code == 200, resp.data
    assert resp.data[0]["status"] != "paid"


def test_cancelar_pagamento_requires_admin(client: APIClient):
    """Mesmo racional de `test_registrar_pagamento_requires_admin`: usa
    `DIRECTOR` (tem `_can_read`, não tem `_can_manage`) para o pagamento
    rejeitado, isolando o guard de `_can_manage` de `cancelar_pagamento`."""
    tenant, admin = _org("finapi6b")
    with use_tenant(tenant.id):
        member = UserService().create_user(
            username="membro_api6b", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
        director = UserService().create_user(
            username="director_fin6b", password="supersecret123",
            role_codes=[RoleCode.DIRECTOR], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "plan": "associado", "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )
    paid = client.post(
        "/api/dues/registrar-pagamento",
        {
            "user": str(member.id),
            "amount": "100.00",
            "method": "dinheiro",
            "paid_at": _dt_str(0),
        },
        format="json",
    )
    due_id = paid.data[0]["id"]

    client.force_authenticate(director)
    resp = client.post(f"/api/dues/{due_id}/cancelar-pagamento")
    assert resp.status_code == 422, resp.data


def test_dues_cannot_be_deleted_directly(client: APIClient):
    tenant, admin = _org("finapi7")
    with use_tenant(tenant.id):
        member = UserService().create_user(
            username="membro_api7", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "plan": "associado", "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )
    due = client.get(f"/api/dues?user={member.id}").data["results"][0]
    assert client.delete(f"/api/dues/{due['id']}").status_code == 405


def test_dues_cannot_be_created_directly(client: APIClient):
    """`Due` só nasce via `registrar-pagamento`/`activate_billing` — um POST
    genérico em /api/dues cai no `create()` herdado do `ModelViewSet`, que
    nunca é chamado pelas ações nomeadas. `DueSerializer` marca todo campo
    como `read_only`, então sem o guard explícito o `is_valid()` passaria
    vazio e o `.save()` estouraria um `IntegrityError` (500) — inclusive
    para o Administrador, já que `_can_manage`/`_can_read` só rodam dentro
    das actions nomeadas, nunca neste caminho."""
    tenant, admin = _org("finapi8")
    client.force_authenticate(admin)
    resp = client.post("/api/dues", {}, format="json")
    assert resp.status_code == 405, resp.data


def test_cancelar_pagamento_on_unknown_due_returns_404(client: APIClient):
    """`cancelar_pagamento` chamava `self.service.cancel_payment(due_id=pk)`
    direto, que faz `self.dues.get(due_id)` internamente — para um `due_id`
    inexistente (ou de outro tenant) isso levanta `Due.DoesNotExist`, que o
    `api_exception_handler` não traduz, virando 500. `self.get_object()`
    faz o mesmo lookup escopado por tenant só que via o caminho padrão do
    DRF, que levanta `Http404` (-> 404 limpo)."""
    import uuid

    tenant, admin = _org("finapi9")
    client.force_authenticate(admin)
    resp = client.post(f"/api/dues/{uuid.uuid4()}/cancelar-pagamento")
    assert resp.status_code == 404, resp.data


def test_finance_dashboard_requires_staff_read(client: APIClient):
    tenant, admin = _org("finapi8")
    with use_tenant(tenant.id):
        plain = UserService().create_user(
            username="plain_fin8", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(plain)
    assert client.get("/api/finance/dashboard").status_code == 422

    client.force_authenticate(admin)
    resp = client.get("/api/finance/dashboard")
    assert resp.status_code == 200, resp.data
    assert "total_users" in resp.data


def test_finance_me_returns_own_summary_or_404(client: APIClient):
    tenant, admin = _org("finapi9")
    with use_tenant(tenant.id):
        member = UserService().create_user(
            username="membro_api9", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
        not_billed = UserService().create_user(
            username="membro_api9b", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "plan": "associado", "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )

    client.force_authenticate(member)
    resp = client.get("/api/finance/me")
    assert resp.status_code == 200, resp.data
    assert "financial_status" in resp.data

    client.force_authenticate(not_billed)
    assert client.get("/api/finance/me").status_code == 404


def test_activate_billing_reactivates_previously_deactivated_profile(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro17", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0)
        )
        FinanceService().deactivate_billing(profile=profile)
        reactivated = FinanceService().activate_billing(
            user=user, plan=PlanCode.ASSOCIADO, due_day=15, started_period=_period(0)
        )
    assert reactivated.id == profile.id
    assert reactivated.is_active is True
    assert reactivated.due_day == 15


def test_reactivate_billing_via_api(client: APIClient):
    tenant, admin = _org("finapi10")
    with use_tenant(tenant.id):
        member = UserService().create_user(
            username="membro_api10", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    created = client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "plan": "associado", "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )
    profile_id = created.data["id"]
    client.post(f"/api/billing-profiles/{profile_id}/desativar")
    resp = client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "plan": "associado", "due_day": 12, "started_period": _period_str(0)},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["id"] == profile_id
    assert resp.data["is_active"] is True
    assert resp.data["due_day"] == 12


def test_dashboard_payments_received_excludes_non_finance_payments(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro18", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0))
        FinanceService().register_payment(
            user=user, amount=Decimal("100.00"), method="dinheiro", paid_at=_dt(0),
        )
        Payment.objects.create(
            tenant_id=tenant_a.id, provider="", method="dinheiro", amount=Decimal("999.00"),
            status=PaymentStatus.APPROVED, payer_id=user.id, paid_at=_dt(0),
            description="Barbearia — corte", created_by_id=None,
        )
        data = FinanceService().dashboard()
    assert data["payments_received"] == Decimal("100.00")


def test_register_payment_immediately_consumes_existing_credit(tenant_a):
    """R$140 fecha o mês corrente (100) + 40 de crédito. R$60 completa o
    crédito em 100 — deve fechar o próximo mês NA HORA (sem rodar roll_all)."""
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro20", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0)
        )
        FinanceService().register_payment(
            user=user, amount=Decimal("140.00"), method="dinheiro", paid_at=_dt(0),
        )
        settled_2 = FinanceService().register_payment(
            user=user, amount=Decimal("60.00"), method="dinheiro", paid_at=_dt(0),
        )
        paid_periods = set(
            Due.objects.filter(billing_profile=profile, status=DueStatus.PAID).values_list(
                "period", flat=True
            )
        )
    assert _period(1) in paid_periods
    assert any(d.period == _period(1) for d in settled_2)


def test_dashboard_advance_payments_received_nets_consumed_credit(tenant_a):
    """Mesmo cenário do teste acima: depois que o crédito acumulado fecha uma
    mensalidade, o saldo líquido de crédito (soma de todos os FinanceCredit,
    não só OVERPAYMENT) deve cair pra zero — não continuar contando os 100
    de OVERPAYMENT como se ainda estivessem disponíveis."""
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro19", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0))
        FinanceService().register_payment(
            user=user, amount=Decimal("140.00"), method="dinheiro", paid_at=_dt(0),
        )
        FinanceService().register_payment(
            user=user, amount=Decimal("60.00"), method="dinheiro", paid_at=_dt(0),
        )
        data = FinanceService().dashboard()
    assert data["advance_payments_received"] == Decimal("0.00")


def test_register_payment_rejects_absurdly_large_amount(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro21", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0))
        with pytest.raises(BusinessRuleError):
            FinanceService().register_payment(
                user=user, amount=Decimal("10000.00"), method="dinheiro", paid_at=_dt(0),
            )


def test_activate_billing_rejects_started_period_too_far_in_the_past(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro22", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        with pytest.raises(BusinessRuleError):
            FinanceService().activate_billing(
                user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(-61)
            )


def test_dashboard_and_billing_profiles_are_tenant_isolated(tenant_a, tenant_b):
    with use_tenant(tenant_a.id):
        user_a = UserService().create_user(
            username="membroTA", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(user=user_a, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0))
    with use_tenant(tenant_b.id):
        data_b = FinanceService().dashboard()
        profiles_b = list(FinanceRepository().active_profiles())
    assert data_b["total_users"] == 0
    assert profiles_b == []


@pytest.mark.parametrize(
    "days_late,expected",
    [
        (-6, DueStatus.PENDING),
        (-5, DueStatus.DUE_SOON),
        (-1, DueStatus.DUE_SOON),
        (0, DueStatus.DUE_TODAY),
        (1, DueStatus.OVERDUE),
        (15, DueStatus.OVERDUE),
        (16, DueStatus.DELINQUENT),
    ],
)
def test_status_for_day_thresholds(days_late, expected):
    today = date(2026, 6, 15)
    due_date = today - timedelta(days=days_late)
    assert FinanceService()._status_for(due_date, today) == expected


def test_activate_billing_via_api_rejects_ineligible_plan(client: APIClient):
    tenant, admin = _org("finapi11")
    with use_tenant(tenant.id):
        coronel = UserService().create_user(
            username="coronel_api", password="supersecret123",
            posto_graduacao="Cel", tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    resp = client.post(
        "/api/billing-profiles",
        {"user": str(coronel.id), "plan": "barbearia", "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )
    assert resp.status_code == 422, resp.data


def test_generate_associado_invite_requires_admin(client: APIClient):
    tenant, admin = _org("finapi12")
    with use_tenant(tenant.id):
        cabo = UserService().create_user(
            username="cabo_convite", password="supersecret123",
            posto_graduacao="Cb", tenant_id=tenant.id,
        )
        director = UserService().create_user(
            username="director_convite", password="supersecret123",
            role_codes=[RoleCode.DIRECTOR], posto_graduacao="Cel", tenant_id=tenant.id,
        )
    client.force_authenticate(director)
    resp = client.post("/api/finance/convites-associado", {"user": str(cabo.id)}, format="json")
    assert resp.status_code == 422, resp.data

    client.force_authenticate(admin)
    resp = client.post("/api/finance/convites-associado", {"user": str(cabo.id)}, format="json")
    assert resp.status_code == 201, resp.data
    assert resp.data["used_at"] is None


def test_generate_associado_invite_rejects_ineligible_rank(tenant_a):
    with use_tenant(tenant_a.id):
        soldado_ev = UserService().create_user(
            username="sdev_convite", password="supersecret123",
            posto_graduacao="Sd EV", tenant_id=tenant_a.id,
        )
        with pytest.raises(BusinessRuleError):
            FinanceService().generate_associado_invite(user=soldado_ev)


def test_accept_associado_invite_activates_the_associado_plan(tenant_a):
    with use_tenant(tenant_a.id):
        cabo = UserService().create_user(
            username="cabo_aceita", password="supersecret123",
            posto_graduacao="Cb", tenant_id=tenant_a.id,
        )
        assert cabo.has_role(RoleCode.BARBERSHOP_CLIENT)
        invite = FinanceService().generate_associado_invite(user=cabo)
        profile = FinanceService().accept_associado_invite(token=invite.token, actor=cabo)
        invite.refresh_from_db()
        cabo.refresh_from_db()
    assert profile.plan == PlanCode.ASSOCIADO
    assert profile.is_active is True
    assert invite.used_at is not None
    # Aceitar o convite troca o perfil de acesso: Cliente da Barbearia (sem
    # patrimônio) vira Usuário (já reserva bens) — RN da correção reportada.
    assert list(cabo.roles.values_list("code", flat=True)) == [RoleCode.USER]


def test_activate_billing_associado_full_grants_patrimonio_access(tenant_a):
    """Mesma troca de perfil, agora pela ativação direta do administrador
    (sem passar por convite) — os dois caminhos usam activate_billing."""
    with use_tenant(tenant_a.id):
        for posto in ("Cb", "Sd EP"):
            membro = UserService().create_user(
                username=f"associado_full_{posto.lower().replace(' ', '')}",
                password="supersecret123", posto_graduacao=posto, tenant_id=tenant_a.id,
            )
            assert membro.has_role(RoleCode.BARBERSHOP_CLIENT)
            FinanceService().activate_billing(
                user=membro, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0),
            )
            membro.refresh_from_db()
            assert list(membro.roles.values_list("code", flat=True)) == [RoleCode.USER]


def test_activate_billing_barbearia_plan_keeps_cb_as_barbershop_client(tenant_a):
    """Assinatura Barbearia não dá acesso ao patrimônio — Cb continua
    Cliente da Barbearia mesmo depois de ativar o plano."""
    with use_tenant(tenant_a.id):
        cabo = UserService().create_user(
            username="cabo_so_barbearia", password="supersecret123",
            posto_graduacao="Cb", tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(
            user=cabo, plan=PlanCode.BARBEARIA, due_day=10, started_period=_period(0),
        )
        cabo.refresh_from_db()
    assert list(cabo.roles.values_list("code", flat=True)) == [RoleCode.BARBERSHOP_CLIENT]


def test_activate_billing_does_not_touch_roles_outside_forced_ranks(tenant_a):
    """Postos que nunca foram forçados pro Cliente da Barbearia não têm o
    perfil mexido pela ativação do Associado Full — grant/revoke são
    no-op fora de Cb/Sd EP/Sd EV."""
    with use_tenant(tenant_a.id):
        coronel = UserService().create_user(
            username="coronel_associado", password="supersecret123",
            posto_graduacao="Cel", role_codes=[RoleCode.DIRECTOR], tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(
            user=coronel, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0),
        )
        coronel.refresh_from_db()
    assert list(coronel.roles.values_list("code", flat=True)) == [RoleCode.DIRECTOR]


def test_accept_associado_invite_rejects_someone_elses_token(tenant_a):
    with use_tenant(tenant_a.id):
        cabo = UserService().create_user(
            username="cabo_dono", password="supersecret123",
            posto_graduacao="Cb", tenant_id=tenant_a.id,
        )
        outro = UserService().create_user(
            username="outro_usuario", password="supersecret123",
            posto_graduacao="Cb", tenant_id=tenant_a.id,
        )
        invite = FinanceService().generate_associado_invite(user=cabo)
        with pytest.raises(BusinessRuleError):
            FinanceService().accept_associado_invite(token=invite.token, actor=outro)


def test_accept_associado_invite_rejects_used_token(tenant_a):
    with use_tenant(tenant_a.id):
        cabo = UserService().create_user(
            username="cabo_reuso", password="supersecret123",
            posto_graduacao="Cb", tenant_id=tenant_a.id,
        )
        invite = FinanceService().generate_associado_invite(user=cabo)
        FinanceService().accept_associado_invite(token=invite.token, actor=cabo)
        with pytest.raises(BusinessRuleError):
            FinanceService().accept_associado_invite(token=invite.token, actor=cabo)


def test_accept_associado_invite_rejects_expired_token(tenant_a):
    with use_tenant(tenant_a.id):
        cabo = UserService().create_user(
            username="cabo_expirado", password="supersecret123",
            posto_graduacao="Cb", tenant_id=tenant_a.id,
        )
        invite = FinanceService().generate_associado_invite(user=cabo)
        invite.expires_at = timezone.now() - timedelta(days=1)
        invite.save(update_fields=["expires_at"])
        with pytest.raises(BusinessRuleError):
            FinanceService().accept_associado_invite(token=invite.token, actor=cabo)


def test_self_subscribe_activates_barbearia_plan_for_eligible_user(client: APIClient):
    tenant, admin = _org("finapi13")
    with use_tenant(tenant.id):
        cabo = UserService().create_user(
            username="cabo_auto", password="supersecret123",
            posto_graduacao="Cb", tenant_id=tenant.id,
        )
    client.force_authenticate(cabo)
    resp = client.post("/api/finance/me/assinar")
    assert resp.status_code == 201, resp.data
    assert resp.data["plan"] == "barbearia"
    assert resp.data["is_active"] is True


def test_self_subscribe_rejects_ineligible_rank(client: APIClient):
    tenant, admin = _org("finapi14")
    with use_tenant(tenant.id):
        coronel = UserService().create_user(
            username="coronel_auto", password="supersecret123",
            posto_graduacao="Cel", tenant_id=tenant.id,
        )
    client.force_authenticate(coronel)
    resp = client.post("/api/finance/me/assinar")
    assert resp.status_code == 422, resp.data


def test_self_subscribe_rejects_when_already_active(client: APIClient):
    tenant, admin = _org("finapi15")
    with use_tenant(tenant.id):
        cabo = UserService().create_user(
            username="cabo_ja_ativo", password="supersecret123",
            posto_graduacao="Cb", tenant_id=tenant.id,
        )
    client.force_authenticate(cabo)
    client.post("/api/finance/me/assinar")
    resp = client.post("/api/finance/me/assinar")
    assert resp.status_code == 422, resp.data


def test_initiate_pix_payment_opens_a_pending_charge(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro_pix1", password="supersecret123", email="membro_pix1@example.com",
            posto_graduacao="Cel", tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0)
        )
        payment = FinanceService().initiate_pix_payment(user=user, amount=Decimal("100.00"))
        profile.refresh_from_db()
    assert payment.status == "pending"
    assert payment.qr_code
    assert profile.pending_payment_id == payment.id


def test_initiate_pix_payment_rejects_when_one_is_already_open(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro_pix2", password="supersecret123", email="membro_pix2@example.com",
            posto_graduacao="Cel", tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(
            user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0)
        )
        FinanceService().initiate_pix_payment(user=user, amount=Decimal("100.00"))
        with pytest.raises(BusinessRuleError):
            FinanceService().initiate_pix_payment(user=user, amount=Decimal("100.00"))


def test_initiate_pix_payment_rejects_when_not_in_billing(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro_pix3", password="supersecret123", email="membro_pix3@example.com",
            posto_graduacao="Cel", tenant_id=tenant_a.id,
        )
        with pytest.raises(BusinessRuleError):
            FinanceService().initiate_pix_payment(user=user, amount=Decimal("100.00"))


def test_initiate_pix_payment_rejects_amount_below_the_plan_fee(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro_pix7", password="supersecret123", email="membro_pix7@example.com",
            posto_graduacao="Cel", tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(
            user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0)
        )
        with pytest.raises(BusinessRuleError):
            FinanceService().initiate_pix_payment(user=user, amount=Decimal("50.00"))


def test_initiate_pix_payment_rejects_amount_not_a_multiple_of_the_fee(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro_pix8", password="supersecret123", email="membro_pix8@example.com",
            posto_graduacao="Cel", tenant_id=tenant_a.id,
        )
        FinanceService().activate_billing(
            user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0)
        )
        with pytest.raises(BusinessRuleError):
            FinanceService().initiate_pix_payment(user=user, amount=Decimal("150.00"))


def test_approved_pix_payment_settles_the_open_dues(tenant_a):
    from apps.finance.tests.conftest import FINANCE_PROVIDER_STATUS

    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro_pix4", password="supersecret123", email="membro_pix4@example.com",
            posto_graduacao="Cel", tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0)
        )
        aberto = FinanceService().initiate_pix_payment(user=user, amount=Decimal("100.00"))
        FINANCE_PROVIDER_STATUS["value"] = "approved"
        payment = FinanceService().refresh_pix_payment(user=user, payment_id=aberto.id)
        profile.refresh_from_db()

    assert payment.status == "approved"
    assert profile.pending_payment_id is None
    paid = Due.objects.filter(billing_profile=profile, status=DueStatus.PAID)
    assert paid.count() == 1
    assert paid.first().settled_by_id == payment.id

    # A tela do QR consulta de novo depois de aprovado (React Query não para
    # de repente) — mesmo sem `pending_payment` mais no perfil, o status
    # final tem que continuar visível por id (achado ao testar ao vivo: a
    # 1ª versão dependia do pending_payment do perfil e "sumia" depois de
    # liquidado, deixando a tela presa em "aguardando").
    with use_tenant(tenant_a.id):
        de_novo = FinanceService().refresh_pix_payment(user=user, payment_id=aberto.id)
    assert de_novo.status == "approved"


def test_expired_pix_payment_does_not_settle_and_clears_pending(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro_pix5", password="supersecret123", email="membro_pix5@example.com",
            posto_graduacao="Cel", tenant_id=tenant_a.id,
        )
        profile = FinanceService().activate_billing(
            user=user, plan=PlanCode.ASSOCIADO, due_day=10, started_period=_period(0)
        )
        payment = FinanceService().initiate_pix_payment(user=user, amount=Decimal("100.00"))
        payment.expires_at = timezone.now() - timedelta(minutes=1)
        payment.save(update_fields=["expires_at"])
        atualizado = FinanceService().refresh_pix_payment(user=user, payment_id=payment.id)
        profile.refresh_from_db()

    assert atualizado.status == "expired"
    assert profile.pending_payment_id is None
    assert Due.objects.filter(billing_profile=profile, status=DueStatus.PAID).count() == 0


def test_settle_finance_payment_for_ignores_non_finance_payments(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="membro_pix6", password="supersecret123", email="membro_pix6@example.com",
            posto_graduacao="Cel", tenant_id=tenant_a.id,
        )
        payment = Payment.objects.create(
            tenant_id=tenant_a.id, provider="", method="pix", amount=Decimal("15.00"),
            status=PaymentStatus.APPROVED, payer_id=user.id, description="Barbearia — corte",
        )
        settled = FinanceService().settle_finance_payment_for(payment)
    assert settled == []


def test_initiate_pix_payment_via_api_requires_email(client: APIClient):
    tenant, admin = _org("finapi16")
    with use_tenant(tenant.id):
        sememail = UserService().create_user(
            username="sememail", password="supersecret123",
            posto_graduacao="Cel", tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    client.post(
        "/api/billing-profiles",
        {"user": str(sememail.id), "plan": "associado", "due_day": 10,
         "started_period": _period_str(0)},
        format="json",
    )
    client.force_authenticate(sememail)
    resp = client.post("/api/finance/me/pagar", {"amount": "100.00"}, format="json")
    assert resp.status_code == 422, resp.data
    assert resp.data["error"]["code"] == "payer_email_required"


def test_initiate_and_check_pix_payment_via_api(client: APIClient):
    tenant, admin = _org("finapi17")
    with use_tenant(tenant.id):
        user = UserService().create_user(
            username="membro_pixapi", password="supersecret123",
            email="membro_pixapi@example.com", posto_graduacao="Cel", tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    client.post(
        "/api/billing-profiles",
        {"user": str(user.id), "plan": "associado", "due_day": 10,
         "started_period": _period_str(0)},
        format="json",
    )
    client.force_authenticate(user)
    resp = client.post("/api/finance/me/pagar", {"amount": "100.00"}, format="json")
    assert resp.status_code == 201, resp.data
    assert resp.data["status"] == "pending"

    status_resp = client.get(f"/api/finance/me/pagamento/{resp.data['id']}")
    assert status_resp.status_code == 200, status_resp.data
    assert status_resp.data["status"] == "pending"
