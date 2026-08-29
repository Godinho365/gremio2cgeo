# Módulo Financeiro (Fase 1 — Núcleo) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core of the Financial module — recurring monthly dues per
user, automatic generation, manual payment registration with automatic
advance-payment allocation, per-period and per-user status tracking, history,
and an admin dashboard. No Pix/online payment yet (Fase 2, separate plan).

**Architecture:** New Django app `apps/finance`, following the project's
`View/Serializer → Service → Repository → Model` layering. Reuses the
existing generic `apps/payments.Payment` model for receipts (extended with
manual payment methods) instead of inventing a parallel concept. A daily
Celery beat task rolls the generation window forward and recomputes
time-derived statuses. Frontend replaces the `FinancePage.tsx` stub with a
real dashboard + admin table + per-user statement, and adds a read-only
"Minha mensalidade" card to the user's own profile page.

**Tech Stack:** Django 5 + DRF (backend), React + TS + react-router-dom +
TanStack Query (frontend), pytest/pytest-django (backend tests), Celery beat
(scheduled task). Docker Compose stack is already running — use
`docker compose exec backend ...` / `docker compose exec frontend ...` for
every command below, from the repo root
`D:\Gremio 2CGEO\Projetos\systempatri_gremio`.

## Global Constraints

- Multi-tenant always: every new query goes through `TenantScopedModel` /
  `BaseRepository`, which already enforce this.
- Layering: business logic (generation, allocation, status computation) lives
  only in `apps/finance/services.py`. Views translate HTTP↔data; models hold
  no logic beyond `__str__`/simple properties.
- DRY: reuse `apps/payments.Payment` for receipts (don't invent a parallel
  payment model); reuse the `apps/payments.CreditEntry` *pattern* (ledger of
  signed amounts, balance = sum) for `FinanceCredit`, not a stored balance
  field. Reuse a single shared rank constant (`BARBERSHOP_ONLY_RANKS`) between
  `apps.accounts` and `apps.finance` instead of duplicating the `{"Sd","Cb"}`
  literal.
- Migrations are never edited after being applied — only new migration files.
- Exact values: monthly fee is a single tenant-wide value from the
  `MEMBERSHIP_FEE` env var (same pattern as `WALK_IN_PRICE`). "Próximo do
  vencimento" = due_date within 5 days. "Vencido" = 1–15 days late.
  "Inadimplente" = more than 15 days late. Sd/Cb (posto/graduação) never
  enter the financial relation — checked directly on `posto_graduacao`, not
  via the `barbershop_client` role (independent rules that currently
  coincide).
- Management/write actions (activate billing, register/cancel payment, edit
  due day): Administrador only. Read (dashboard, listings): Admin, Diretor,
  Inventariante, Auditor (the existing "staff" group). Every user can read
  their own summary via `/api/finance/me`.
- Domain/UI text in PT-BR; identifiers in English (existing repo convention).
- Spec of record: `docs/superpowers/specs/2026-08-29-modulo-financeiro-fase1-design.md`.

**Note on one plan-time refinement vs. the spec:** the spec described the
Sd/Cb auto-deactivation as "a hook called from `UserService`". While planning
the exact code, this would create a backwards dependency (`apps.accounts`
importing `apps.finance`, when every other app depends *on* `apps.accounts`,
never the reverse). This plan instead has the **daily Celery task**
reconcile it — for every active `BillingProfile`, if the user's current
`posto_graduacao` is Sd/Cb, deactivate before doing anything else. Same
outcome (auto-deactivation, no manual step), just reached by the existing
daily reconciliation pass instead of a live cross-app hook, keeping
`apps.finance` the only side that knows about `apps.accounts` (never the
reverse). Detail, not a scope change — flagged here for visibility.

**Note on a bug this plan's own sample code had, found only by Task 14's
manual browser verification:** both modal components (`ActivateBillingModal`
in Task 11, `RegisterPaymentModal` in Task 12) were originally written with
`<div className="modal-backdrop fade show" />` as the LAST CHILD inside the
outer `<div className="modal ...">`, instead of as that div's SIBLING inside
a `<>...</>` fragment (the pattern every other modal in this codebase, e.g.
`UsersPage.tsx`, actually uses). This is syntactically valid JSX — `eslint`
and `tsc` have no way to flag it — but it's wrong at the DOM/CSS level: with
the backdrop nested inside `.modal` instead of a sibling, browser stacking
order puts the backdrop (a `position: fixed` layer) in front of the modal's
own buttons within their shared parent, silently swallowing every click on
"Ativar"/"Registrar"/"Cancelar" inside the modal. No automated test or code
review caught this (none of them render the app in an actual browser); it
was only found during Task 14 when the "Ativar cobrança" button turned out
to be unclickable. Both files were corrected in-place, and the fix (shown
below in Tasks 11 and 12's code) is what actually shipped. If you're
adapting this plan's pattern for a new modal elsewhere, use the fragment
form (`<>`, `.modal` wrapper, `.modal-backdrop` sibling, `</>`), not a
single enclosing `<div className="modal ...">`.

---

## File Structure

Backend — new app `apps/finance`:
- `backend/apps/finance/models.py` — `BillingProfile`, `Due`, `FinanceCredit` + `DueStatus`, `FinancialStatus`, `FinanceCreditReason` choices, `membership_fee()` helper.
- `backend/apps/finance/repositories.py` — `FinanceRepository` (BillingProfile), `DueRepository`.
- `backend/apps/finance/services.py` — `FinanceService`: generation, allocation, status computation, dashboard aggregation. All business rules live here.
- `backend/apps/finance/tasks.py` — `roll_dues` Celery task.
- `backend/apps/finance/api/serializers.py`, `backend/apps/finance/api/views.py` — HTTP layer.
- `backend/apps/finance/tests/test_finance.py` — all backend tests for this module (single file, matching this repo's per-app convention).

Backend — touched existing files:
- `backend/apps/accounts/models.py` — shared `BARBERSHOP_ONLY_RANKS` constant.
- `backend/apps/accounts/services.py` — `UserService` now imports the shared constant instead of owning it.
- `backend/apps/payments/models.py` — `PaymentMethod` gains `DINHEIRO`/`TRANSFERENCIA`.
- `backend/apps/payments/migrations/0003_alter_payment_method.py` — new migration for the choice change.
- `backend/config/settings/base.py` — `apps.finance` in `INSTALLED_APPS`, `MEMBERSHIP_FEE` setting, `CELERY_BEAT_SCHEDULE` entry, `ENUM_NAME_OVERRIDES` entries.
- `backend/.env.example` — `MEMBERSHIP_FEE=100.00`.
- `backend/config/api_urls.py` — router registrations + the two standalone views.

Frontend:
- `frontend/src/features/finance/api.ts` — new, TanStack Query hooks.
- `frontend/src/modules.ts` — `financeiro.available = true`.
- `frontend/src/pages/FinancePage.tsx` — rewritten (was a stub).
- `frontend/src/pages/FinanceStatementPage.tsx` — new, per-user extrato.
- `frontend/src/App.tsx` — new nested route for the statement page.
- `frontend/src/pages/ProfilePage.tsx` — new "Minha mensalidade" card.

---

### Task 1: Finance app scaffold, models, migrations, shared rank constant

**Files:**
- Modify: `backend/apps/accounts/models.py:14-20` (add constant after `RoleCode`)
- Modify: `backend/apps/accounts/services.py:23-24` (use the shared constant)
- Modify: `backend/apps/payments/models.py:27-29` (`PaymentMethod`)
- Create: `backend/apps/payments/migrations/0003_alter_payment_method.py`
- Create: `backend/apps/finance/__init__.py`, `backend/apps/finance/apps.py`, `backend/apps/finance/models.py`, `backend/apps/finance/migrations/__init__.py`, `backend/apps/finance/migrations/0001_initial.py`, `backend/apps/finance/tests/__init__.py`
- Modify: `backend/config/settings/base.py` (`INSTALLED_APPS`, `MEMBERSHIP_FEE`, `ENUM_NAME_OVERRIDES`)
- Modify: `backend/.env.example`
- Test: `backend/apps/finance/tests/test_finance.py` (new)

**Interfaces:**
- Produces: `apps.accounts.models.BARBERSHOP_ONLY_RANKS: frozenset[str]` (consumed by Task 6 and by `UserService`). `apps.finance.models.{BillingProfile, Due, FinanceCredit, DueStatus, FinancialStatus, FinanceCreditReason, OPEN_DUE_STATUSES, membership_fee}` (consumed by every later backend task). `apps.payments.models.PaymentMethod.{DINHEIRO, TRANSFERENCIA}` (consumed by Task 3).

- [ ] **Step 1: Move the rank constant to `apps/accounts/models.py`**

In `backend/apps/accounts/models.py`, the `RoleCode` class ends at line 20
(`BARBERSHOP_CLIENT = "barbershop_client", "Cliente da Barbearia"`). Add,
right after the `RoleCode` class definition:

```python
class RoleCode(models.TextChoices):
    ADMIN = "admin", "Administrador"
    DIRECTOR = "director", "Diretor(a) Patrimonial"
    INVENTORY = "inventory", "Inventariante"
    USER = "user", "Usuário"
    AUDITOR = "auditor", "Auditor"
    BARBERSHOP = "barbershop", "Administrador da Barbearia"
    BARBERSHOP_CLIENT = "barbershop_client", "Cliente da Barbearia"


# Praças (Sd/Cb) têm regras próprias em mais de um módulo (perfil de acesso,
# relação financeira) — uma única fonte de verdade evita duplicar o literal.
BARBERSHOP_ONLY_RANKS = frozenset({"Sd", "Cb"})
```

In `backend/apps/accounts/services.py`, change the import on line 19 from:

```python
from .models import RoleCode, User
```

to:

```python
from .models import BARBERSHOP_ONLY_RANKS, RoleCode, User
```

Then remove the now-duplicate class attribute (line 24) and the reference to
it in `_forced_roles_for_rank` (line 46). Change:

```python
class UserService(BaseService):
    _BARBERSHOP_ONLY_RANKS = frozenset({"Sd", "Cb"})

    def __init__(
```

to:

```python
class UserService(BaseService):
    def __init__(
```

And change:

```python
    def _forced_roles_for_rank(self, posto_graduacao: str) -> list[str] | None:
        """Praças (Sd/Cb) só têm o perfil Cliente da Barbearia — regra de hierarquia."""
        if posto_graduacao in self._BARBERSHOP_ONLY_RANKS:
            return [RoleCode.BARBERSHOP_CLIENT]
        return None
```

to:

```python
    def _forced_roles_for_rank(self, posto_graduacao: str) -> list[str] | None:
        """Praças (Sd/Cb) só têm o perfil Cliente da Barbearia — regra de hierarquia."""
        if posto_graduacao in BARBERSHOP_ONLY_RANKS:
            return [RoleCode.BARBERSHOP_CLIENT]
        return None
```

- [ ] **Step 2: Run the accounts test suite to confirm the refactor didn't break anything**

Run: `docker compose exec backend pytest apps/accounts/tests/test_auth_and_rbac.py -q`
Expected: PASS (same tests as before — this is a pure rename/relocation, no behavior change).

- [ ] **Step 3: Extend `PaymentMethod` and add its migration**

In `backend/apps/payments/models.py`, change:

```python
class PaymentMethod(models.TextChoices):
    PIX = "pix", "Pix"
```

to:

```python
class PaymentMethod(models.TextChoices):
    PIX = "pix", "Pix"
    DINHEIRO = "dinheiro", "Dinheiro"
    TRANSFERENCIA = "transferencia", "Transferência"
```

Create `backend/apps/payments/migrations/0003_alter_payment_method.py`:

```python
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0002_creditentry"),
    ]

    operations = [
        migrations.AlterField(
            model_name="payment",
            name="method",
            field=models.CharField(
                choices=[
                    ("pix", "Pix"),
                    ("dinheiro", "Dinheiro"),
                    ("transferencia", "Transferência"),
                ],
                default="pix",
                max_length=20,
            ),
        ),
    ]
```

- [ ] **Step 4: Write the finance app scaffold**

Create `backend/apps/finance/__init__.py` (empty file).

Create `backend/apps/finance/apps.py`:

```python
from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.finance"
    label = "finance"
```

Create `backend/apps/finance/migrations/__init__.py` (empty file).

Create `backend/apps/finance/tests/__init__.py` (empty file).

- [ ] **Step 5: Write the failing test for the models**

Create `backend/apps/finance/tests/test_finance.py`:

```python
"""Módulo Financeiro (Fase 1): mensalidades, alocação de pagamento, status."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
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
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.finance.models'` (the app doesn't exist yet).

- [ ] **Step 7: Write the models**

Create `backend/apps/finance/models.py`:

```python
"""Financeiro — mensalidades (Fase 1: núcleo).

BillingProfile: quem está na relação financeira e as regras dele (dia de
vencimento, desde quando). Due: uma mensalidade de um mês específico — no
máximo uma por (billing_profile, period). FinanceCredit: extrato de crédito
por resto de pagamento, mesmo padrão do CreditEntry da barbearia (saldo é a
soma das linhas, nunca um campo solto).
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.payments.models import Payment
from core.models import TenantScopedModel


def membership_fee() -> Decimal:
    """Valor da mensalidade, de MEMBERSHIP_FEE no .env (padrão R$ 100,00).

    Lido a cada uso: mudar o valor não exige mexer no código, e a mensalidade
    já gerada fica congelada (snapshot em Due.amount).
    """
    return Decimal(str(settings.MEMBERSHIP_FEE))


class FinancialStatus(models.TextChoices):
    UP_TO_DATE = "up_to_date", "Em dia"
    PAID_IN_ADVANCE = "paid_in_advance", "Pago antecipadamente"
    DUE_SOON = "due_soon", "Próximo do vencimento"
    DUE_TODAY = "due_today", "Vencendo hoje"
    OVERDUE = "overdue", "Vencido"
    DELINQUENT = "delinquent", "Inadimplente"


class BillingProfile(TenantScopedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="billing_profile"
    )
    due_day = models.PositiveSmallIntegerField()
    started_period = models.DateField()
    is_active = models.BooleanField(default=True)
    financial_status = models.CharField(
        max_length=20, choices=FinancialStatus.choices, default=FinancialStatus.UP_TO_DATE
    )
    last_payment_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "billing_profile"

    def __str__(self) -> str:
        return f"Mensalidade de {self.user}"


class DueStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    DUE_SOON = "due_soon", "Próximo do vencimento"
    DUE_TODAY = "due_today", "Vencendo hoje"
    OVERDUE = "overdue", "Vencido"
    DELINQUENT = "delinquent", "Inadimplente"
    PAID = "paid", "Pago"


OPEN_DUE_STATUSES = (
    DueStatus.PENDING,
    DueStatus.DUE_SOON,
    DueStatus.DUE_TODAY,
    DueStatus.OVERDUE,
    DueStatus.DELINQUENT,
)


class Due(TenantScopedModel):
    billing_profile = models.ForeignKey(
        BillingProfile, on_delete=models.CASCADE, related_name="dues"
    )
    period = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=DueStatus.choices, default=DueStatus.PENDING)
    # True quando liquidada antes do próprio mês (period) começar.
    paid_in_advance = models.BooleanField(default=False)
    settled_by = models.ForeignKey(
        Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="dues_settled"
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "due"
        ordering = ["period"]
        constraints = [
            models.UniqueConstraint(
                fields=["billing_profile", "period"], name="unique_due_period"
            )
        ]
        indexes = [models.Index(fields=["status", "due_date"])]

    def __str__(self) -> str:
        return f"{self.period:%m/%Y} — {self.get_status_display()}"


class FinanceCreditReason(models.TextChoices):
    OVERPAYMENT = "overpayment", "Resto de pagamento"
    CONSUMED = "consumed", "Usado em mensalidade"
    REVERSED = "reversed", "Estornado"
    MANUAL = "manual", "Ajuste da administração"


class FinanceCredit(TenantScopedModel):
    billing_profile = models.ForeignKey(
        BillingProfile, on_delete=models.CASCADE, related_name="credits"
    )
    # Positivo credita, negativo consome/estorna — saldo é sempre a soma.
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=20, choices=FinanceCreditReason.choices)
    payment = models.ForeignKey(
        Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="finance_credits"
    )
    due = models.ForeignKey(
        Due, on_delete=models.SET_NULL, null=True, blank=True, related_name="credit_entries"
    )
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "finance_credit"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        sinal = "+" if self.amount >= 0 else ""
        return f"{sinal}{self.amount} {self.get_reason_display()}"
```

(The inner `from django.conf import settings as django_settings` inside
`membership_fee()` avoids shadowing the module-level `settings` import used
by `AUTH_USER_MODEL` above — both refer to the same `django.conf.settings`
module, this just keeps the name local to the function for clarity.)

- [ ] **Step 8: Generate and review the migration**

Run: `docker compose exec backend python manage.py makemigrations finance`
Expected: creates `backend/apps/finance/migrations/0001_initial.py` with
`CreateModel` for `BillingProfile`, `Due`, `FinanceCredit`. Open the
generated file and confirm the `dependencies` list includes
`("core", "0001_initial")`, `("payments", "0003_alter_payment_method")` (from
this same task, since `Due`/`FinanceCredit` FK to `Payment`), and
`migrations.swappable_dependency(settings.AUTH_USER_MODEL)`. If Django didn't
pick up the `payments` dependency automatically, add it by hand — the FK to
`Payment` requires it.

- [ ] **Step 9: Register the app, add settings**

In `backend/config/settings/base.py`, change `INSTALLED_APPS` (currently
ending with `"apps.payments",`):

```python
    "apps.barbershop",
    "apps.payments",
]
```

to:

```python
    "apps.barbershop",
    "apps.payments",
    "apps.finance",
]
```

Add near `WALK_IN_PRICE` (in the "Pagamentos (Mercado Pago)" section):

```python
# Valor único da mensalidade do grêmio (módulo Financeiro).
MEMBERSHIP_FEE = env("MEMBERSHIP_FEE", default="100.00")
```

In `ENUM_NAME_OVERRIDES` (currently ending with `"PaymentStatusEnum": ...`),
add:

```python
        "PaymentStatusEnum": "apps.payments.models.PaymentStatus",
        "DueStatusEnum": "apps.finance.models.DueStatus",
        "FinancialStatusEnum": "apps.finance.models.FinancialStatus",
    },
}
```

In `backend/.env.example`, add a line: `MEMBERSHIP_FEE=100.00`.

- [ ] **Step 10: Run migrations and the test**

Run: `docker compose exec backend python manage.py migrate`
Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -v`
Expected: PASS.

- [ ] **Step 11: Run the full backend suite to check for regressions**

Run: `docker compose exec backend pytest -q`
Expected: PASS (this confirms the `PaymentMethod` change and the accounts
refactor didn't break anything elsewhere).

- [ ] **Step 12: Commit**

```bash
git add backend/apps/accounts/models.py backend/apps/accounts/services.py backend/apps/payments/models.py backend/apps/payments/migrations/0003_alter_payment_method.py backend/apps/finance backend/config/settings/base.py backend/.env.example
git commit -m "feat(finance): scaffold app, models, and shared rank constant"
```

---

### Task 2: Generation — `_ensure_window`, `activate_billing`, `due_date` computation

**Files:**
- Create: `backend/apps/finance/repositories.py`
- Create: `backend/apps/finance/services.py`
- Test: `backend/apps/finance/tests/test_finance.py`

**Interfaces:**
- Consumes: `apps.finance.models.*` (Task 1).
- Produces: `FinanceRepository`, `DueRepository` (consumed by every later
  service task). `FinanceService.activate_billing(*, user, due_day,
  started_period, actor_id=None) -> BillingProfile`. `FinanceService.
  _ensure_window`, `_create_due`, `_status_for`, `_compute_financial_status`
  (private, consumed by Tasks 3–7 — same instance methods, same names).
  Module-level `_due_date_for(period, due_day) -> date`, `_first_of_month(d)
  -> date`, `_add_months(d, n) -> date` in `services.py` (consumed by later
  steps in this same file).

- [ ] **Step 1: Write the failing tests**

Append to `backend/apps/finance/tests/test_finance.py`:

```python
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
```

Add `from core.exceptions import BusinessRuleError` to the imports at the top
of `test_finance.py`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.finance.services'`.

- [ ] **Step 3: Write the repository**

Create `backend/apps/finance/repositories.py`:

```python
from __future__ import annotations

from datetime import date

from django.db import models

from core.repositories import BaseRepository

from .models import OPEN_DUE_STATUSES, BillingProfile, Due


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
```

- [ ] **Step 4: Write the service — generation and activation**

Create `backend/apps/finance/services.py`:

```python
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
from core.context import get_current_tenant_id
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
        return Due.objects.create(
            tenant_id=get_current_tenant_id(),
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full backend suite**

Run: `docker compose exec backend pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/apps/finance/repositories.py backend/apps/finance/services.py backend/apps/finance/tests/test_finance.py
git commit -m "feat(finance): due generation, activation, financial status"
```

---

### Task 3: Payment allocation — `register_payment`

**Files:**
- Modify: `backend/apps/finance/services.py`
- Test: `backend/apps/finance/tests/test_finance.py`

**Interfaces:**
- Consumes: `FinanceService` internals from Task 2 (`_ensure_window`,
  `_create_due`, `_compute_financial_status`, `_status_for`,
  `_first_of_month`, `_add_months`).
- Produces: `FinanceService.register_payment(*, user, amount, method,
  paid_at, actor_id=None) -> list[Due]` — the `Due` rows newly marked PAID by
  this call, in chronological order.

- [ ] **Step 1: Write the failing test — the worked example from the spec**

Append to `backend/apps/finance/tests/test_finance.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -k register_payment -v`
Expected: FAIL — `AttributeError: 'FinanceService' object has no attribute 'register_payment'`.

- [ ] **Step 3: Implement `register_payment`**

In `backend/apps/finance/services.py`, this method needs types Task 2 didn't
import yet. Change the import block at the top of the file from:

```python
import calendar
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import BARBERSHOP_ONLY_RANKS, User
from apps.payments.repositories import PaymentRepository
from core import audit
from core.context import get_current_tenant_id
from core.exceptions import BusinessRuleError
from core.services import BaseService

from .models import BillingProfile, Due, DueStatus, FinancialStatus, membership_fee
from .repositories import DueRepository, FinanceRepository
```

to:

```python
import calendar
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import BARBERSHOP_ONLY_RANKS, User
from apps.payments.models import Payment, PaymentStatus
from apps.payments.repositories import PaymentRepository
from core import audit
from core.context import get_current_tenant_id
from core.exceptions import BusinessRuleError
from core.services import BaseService

from .models import (
    BillingProfile,
    Due,
    DueStatus,
    FinanceCredit,
    FinanceCreditReason,
    FinancialStatus,
    membership_fee,
)
from .repositories import DueRepository, FinanceRepository
```

Then append, to the `FinanceService` class (after `activate_billing`):

```python
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
            self._extend_until(profile, periods_covered, today=paid_at.date())
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
            FinanceCredit.objects.create(
                tenant_id=get_current_tenant_id(),
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -v`
Expected: PASS (all tests in the file, including Tasks 1–2's).

- [ ] **Step 5: Run the full backend suite**

Run: `docker compose exec backend pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/apps/finance/services.py backend/apps/finance/tests/test_finance.py
git commit -m "feat(finance): payment allocation with advance-payment support"
```

---

### Task 4: Payment cancellation — `cancel_payment`

**Files:**
- Modify: `backend/apps/finance/services.py`
- Test: `backend/apps/finance/tests/test_finance.py`

**Interfaces:**
- Consumes: `FinanceService.register_payment` (Task 3).
- Produces: `FinanceService.cancel_payment(*, due_id, actor_id=None) ->
  list[Due]` — every `Due` reopened by cancelling the payment that had
  settled the given `due_id`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/apps/finance/tests/test_finance.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -k cancel_payment -v`
Expected: FAIL — `AttributeError: 'FinanceService' object has no attribute 'cancel_payment'`.

- [ ] **Step 3: Implement `cancel_payment`**

In `backend/apps/finance/services.py`, append to `FinanceService` (after
`register_payment`):

```python
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

        for credit in FinanceCredit.objects.for_current_tenant().filter(
            payment=payment, reason=FinanceCreditReason.OVERPAYMENT
        ):
            FinanceCredit.objects.create(
                tenant_id=get_current_tenant_id(),
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full backend suite**

Run: `docker compose exec backend pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/apps/finance/services.py backend/apps/finance/tests/test_finance.py
git commit -m "feat(finance): payment cancellation reopens settled dues"
```

---

### Task 5: Daily reconciliation — Celery task, credit sweep, Sd/Cb auto-deactivation

**Files:**
- Modify: `backend/apps/finance/services.py`
- Create: `backend/apps/finance/tasks.py`
- Modify: `backend/config/settings/base.py` (`CELERY_BEAT_SCHEDULE`)
- Test: `backend/apps/finance/tests/test_finance.py`

**Interfaces:**
- Consumes: everything from Tasks 2–4.
- Produces: `FinanceService.deactivate_billing(*, profile, actor_id=None) ->
  BillingProfile`. `FinanceService.roll_all() -> int` (per-tenant reconcile
  pass, consumed by the Celery task). `apps.finance.tasks.roll_dues` (Celery
  task name `"finance.roll_dues"`).

- [ ] **Step 1: Write the failing tests**

Append to `backend/apps/finance/tests/test_finance.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -k "roll_all or roll_dues" -v`
Expected: FAIL — `AttributeError: 'FinanceService' object has no attribute 'deactivate_billing'` (and `roll_all`), and `ModuleNotFoundError` for `apps.finance.tasks`.

- [ ] **Step 3: Implement `deactivate_billing`, `_credit_balance`, `_consume_credit`, `roll_all`**

In `backend/apps/finance/services.py`, `_credit_balance` below needs `Sum`,
not imported yet. Change the `from django.db import transaction` line at
the top of the file to:

```python
from django.db import transaction
from django.db.models import Sum
```

Then append, to `FinanceService` (after `cancel_payment`):

```python
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
        total = FinanceCredit.objects.for_current_tenant().filter(
            billing_profile=profile
        ).aggregate(s=Sum("amount"))["s"]
        return total or Decimal("0.00")

    def _consume_credit(self, profile: BillingProfile, today: date) -> None:
        balance = self._credit_balance(profile)
        for due in self.dues.open_for_profile(profile):
            if balance < due.amount:
                break
            due.status = DueStatus.PAID
            due.paid_in_advance = due.period > _first_of_month(today)
            due.paid_at = timezone.now()
            due.save(update_fields=["status", "paid_in_advance", "paid_at", "updated_at"])
            FinanceCredit.objects.create(
                tenant_id=get_current_tenant_id(),
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
```

- [ ] **Step 4: Write the Celery task**

Create `backend/apps/finance/tasks.py`:

```python
"""Tasks Celery do financeiro.

Uma vez por dia: garante a janela de mensalidades futuras, recalcula status
por data, consome crédito acumulado e desativa quem virou Sd/Cb.
"""
from __future__ import annotations

import logging

from celery import shared_task

from core.context import use_tenant
from core.models import Tenant

from .services import FinanceService

logger = logging.getLogger(__name__)


@shared_task(name="finance.roll_dues")
def roll_dues() -> int:
    total = 0
    for tenant in Tenant.objects.filter(is_active=True):
        try:
            with use_tenant(tenant.id):
                total += FinanceService().roll_all()
        except Exception:  # noqa: BLE001 - falha de um tenant não derruba os demais
            logger.exception("Falha ao rolar mensalidades do tenant %s", tenant.id)
    return total
```

- [ ] **Step 5: Register the beat schedule**

In `backend/config/settings/base.py`, change `CELERY_BEAT_SCHEDULE`
(currently ending with the `sync-pending-payments` entry):

```python
    "sync-pending-payments": {
        "task": "payments.sync_pending_payments",
        "schedule": PIX_SYNC_SECONDS,
    },
}
```

to:

```python
    "sync-pending-payments": {
        "task": "payments.sync_pending_payments",
        "schedule": PIX_SYNC_SECONDS,
    },
    # RN-F1: janela de mensalidades, status por data, crédito, Sd/Cb — uma
    # vez por dia é suficiente (nenhum desses efeitos precisa ser imediato).
    "roll-finance-dues": {
        "task": "finance.roll_dues",
        "schedule": crontab(hour=1, minute=0),
    },
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -v`
Expected: PASS.

- [ ] **Step 7: Run the full backend suite**

Run: `docker compose exec backend pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/apps/finance/services.py backend/apps/finance/tasks.py backend/config/settings/base.py backend/apps/finance/tests/test_finance.py
git commit -m "feat(finance): daily reconciliation task (window, status, credit, Sd/Cb)"
```

---

### Task 6: Dashboard and per-user summary aggregation

**Files:**
- Modify: `backend/apps/finance/services.py`
- Test: `backend/apps/finance/tests/test_finance.py`

**Interfaces:**
- Consumes: everything from Tasks 2–5.
- Produces: `FinanceService.summary_for(profile) -> dict` (consumed by
  Task 9's `/api/finance/me` and the extrato screen). `FinanceService.
  dashboard(*, date_from=None, date_to=None) -> dict` (consumed by Task 9's
  `/api/finance/dashboard`).

- [ ] **Step 1: Write the failing tests**

Append to `backend/apps/finance/tests/test_finance.py`:

```python
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
        summary = FinanceService().summary_for(profile)
    assert summary["months_paid"] == 2
    assert summary["months_open"] == 1
    assert summary["paid_through_period"] == _period(1)
    assert summary["pending_amount"] == Decimal("100.00")
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -k "summary_for or dashboard" -v`
Expected: FAIL — `AttributeError: 'FinanceService' object has no attribute 'summary_for'`.

- [ ] **Step 3: Implement `summary_for` and `dashboard`**

In `backend/apps/finance/services.py`, first change the `from .models
import (...)` block at the top of the file (both `summary_for` and
`dashboard` below need `OPEN_DUE_STATUSES`, not imported yet) from:

```python
from .models import (
    BillingProfile,
    Due,
    DueStatus,
    FinanceCredit,
    FinanceCreditReason,
    FinancialStatus,
    membership_fee,
)
```

to:

```python
from .models import (
    OPEN_DUE_STATUSES,
    BillingProfile,
    Due,
    DueStatus,
    FinanceCredit,
    FinanceCreditReason,
    FinancialStatus,
    membership_fee,
)
```

Also change the `from datetime import date, datetime` line at the top to
`from datetime import date, datetime, timedelta` (`dashboard` below needs
`timedelta` for the 30-day cutoff).

Then append, to `FinanceService` (at the end of the class):

```python
    def summary_for(self, profile: BillingProfile) -> dict:
        today = timezone.localdate()
        all_dues = list(self.dues.for_profile(profile).order_by("period"))
        paid = [d for d in all_dues if d.status == DueStatus.PAID]
        open_dues = [d for d in all_dues if d.status in OPEN_DUE_STATUSES]
        next_due = open_dues[0] if open_dues else None
        return {
            "financial_status": profile.financial_status,
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

        payments_qs = self.payments.query().filter(status=PaymentStatus.APPROVED)
        if date_from:
            payments_qs = payments_qs.filter(paid_at__date__gte=date_from)
        if date_to:
            payments_qs = payments_qs.filter(paid_at__date__lte=date_to)
        received = payments_qs.aggregate(s=Sum("amount"))["s"] or Decimal("0.00")

        advance_credit = FinanceCredit.objects.for_current_tenant().filter(
            reason=FinanceCreditReason.OVERPAYMENT
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full backend suite**

Run: `docker compose exec backend pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/apps/finance/services.py backend/apps/finance/tests/test_finance.py
git commit -m "feat(finance): per-user summary and admin dashboard aggregation"
```

---

### Task 7: API — `BillingProfileViewSet`

**Files:**
- Create: `backend/apps/finance/api/__init__.py`
- Create: `backend/apps/finance/api/serializers.py`
- Create: `backend/apps/finance/api/views.py`
- Modify: `backend/config/api_urls.py`
- Test: `backend/apps/finance/tests/test_finance.py`

**Interfaces:**
- Consumes: `FinanceService.{activate_billing, deactivate_billing,
  update_due_day}` (Tasks 2, 5).
- Produces: `BillingProfileSerializer`, `ActivateBillingSerializer`,
  `UpdateDueDaySerializer` (consumed by Task 8's `DueSerializer` file, same
  module). `BillingProfileViewSet`, `_can_read`, `_can_manage` (consumed by
  Task 8). Router path `billing-profiles` (`/api/billing-profiles`).

- [ ] **Step 1: Write the failing tests**

Append to `backend/apps/finance/tests/test_finance.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -k billing_profiles -v`
Expected: FAIL — `404` (route doesn't exist yet).

- [ ] **Step 3: Write the serializers**

Create `backend/apps/finance/api/__init__.py` (empty file).

Create `backend/apps/finance/api/serializers.py`:

```python
from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.accounts.models import User
from apps.payments.models import PaymentMethod
from core.context import get_current_tenant_id

from ..models import BillingProfile, Due


def _tenant_users_queryset():
    tenant_id = get_current_tenant_id()
    return User.objects.filter(tenant_id=tenant_id) if tenant_id else User.objects.none()


class BillingProfileSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.display_name", read_only=True)
    user_posto = serializers.CharField(source="user.posto_graduacao", read_only=True)
    financial_status_label = serializers.CharField(
        source="get_financial_status_display", read_only=True
    )

    class Meta:
        model = BillingProfile
        fields = [
            "id",
            "user",
            "user_name",
            "user_posto",
            "due_day",
            "started_period",
            "is_active",
            "financial_status",
            "financial_status_label",
            "last_payment_at",
        ]
        read_only_fields = ["id", "financial_status", "last_payment_at"]


class ActivateBillingSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.none())
    due_day = serializers.IntegerField(min_value=1, max_value=31)
    started_period = serializers.DateField()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = _tenant_users_queryset()  # type: ignore[attr-defined]


class UpdateDueDaySerializer(serializers.Serializer):
    due_day = serializers.IntegerField(min_value=1, max_value=31)


class DueSerializer(serializers.ModelSerializer):
    user = serializers.UUIDField(source="billing_profile.user_id", read_only=True)
    user_name = serializers.CharField(
        source="billing_profile.user.display_name", read_only=True
    )
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Due
        fields = [
            "id",
            "billing_profile",
            "user",
            "user_name",
            "period",
            "due_date",
            "amount",
            "status",
            "status_label",
            "paid_in_advance",
            "paid_at",
        ]
        read_only_fields = fields


class RegisterPaymentSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.none())
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    paid_at = serializers.DateTimeField()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = _tenant_users_queryset()  # type: ignore[attr-defined]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("O valor deve ser maior que zero.")
        return value
```

(`Due` and `DueSerializer` are defined here now — Task 8 reuses them from
this same file, no separate file needed.)

- [ ] **Step 4: Write `BillingProfileViewSet`**

Create `backend/apps/finance/api/views.py`:

```python
"""Financeiro HTTP layer. Regras no FinanceService; sem lógica aqui."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import RoleCode
from core.exceptions import BusinessRuleError
from core.viewsets import TenantScopedViewSet

from ..models import BillingProfile
from ..services import FinanceService
from .serializers import ActivateBillingSerializer, BillingProfileSerializer, UpdateDueDaySerializer

_READ_ROLES = (RoleCode.ADMIN, RoleCode.DIRECTOR, RoleCode.INVENTORY, RoleCode.AUDITOR)
_MANAGE_ROLES = (RoleCode.ADMIN,)


def _can_read(user) -> bool:
    return user.is_superuser or user.roles.filter(code__in=_READ_ROLES).exists()


def _can_manage(user) -> bool:
    return user.is_superuser or user.roles.filter(code__in=_MANAGE_ROLES).exists()


class BillingProfileViewSet(TenantScopedViewSet):
    serializer_class = BillingProfileSerializer
    queryset = BillingProfile.objects.none()
    service = FinanceService()
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):  # type: ignore[override]
        if not _can_read(self.request.user):
            raise BusinessRuleError("Sem permissão para ver o financeiro.", code="forbidden")
        return self.service.profiles.all().select_related("user").order_by("user__nome_guerra")

    @extend_schema(request=ActivateBillingSerializer, responses={201: BillingProfileSerializer})
    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        if not _can_manage(request.user):
            raise BusinessRuleError("Apenas Administrador ativa cobrança.", code="forbidden")
        payload = ActivateBillingSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        profile = self.service.activate_billing(
            user=payload.validated_data["user"],
            due_day=payload.validated_data["due_day"],
            started_period=payload.validated_data["started_period"],
            actor_id=str(request.user.pk),
        )
        return Response(BillingProfileSerializer(profile).data, status=201)

    @extend_schema(request=UpdateDueDaySerializer, responses={200: BillingProfileSerializer})
    def partial_update(self, request: Request, *args: object, **kwargs: object) -> Response:
        if not _can_manage(request.user):
            raise BusinessRuleError("Apenas Administrador edita o vencimento.", code="forbidden")
        payload = UpdateDueDaySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        profile = self.service.update_due_day(
            profile=self.get_object(),
            due_day=payload.validated_data["due_day"],
            actor_id=str(request.user.pk),
        )
        return Response(BillingProfileSerializer(profile).data)

    @extend_schema(responses={200: BillingProfileSerializer})
    @action(detail=True, methods=["post"], url_path="desativar")
    def desativar(self, request: Request, pk: str = "") -> Response:
        if not _can_manage(request.user):
            raise BusinessRuleError("Apenas Administrador desativa cobrança.", code="forbidden")
        profile = self.service.deactivate_billing(
            profile=self.get_object(), actor_id=str(request.user.pk)
        )
        return Response(BillingProfileSerializer(profile).data)
```

- [ ] **Step 5: Register the route**

In `backend/config/api_urls.py`, add the import (alongside the other
`from apps.X.api.views import ...` lines):

```python
from apps.finance.api.views import BillingProfileViewSet
```

And register it in the router (alongside the other `router.register(...)`
calls):

```python
router.register("billing-profiles", BillingProfileViewSet, basename="billingprofile")
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -v`
Expected: PASS.

- [ ] **Step 7: Run the full backend suite**

Run: `docker compose exec backend pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/apps/finance/api backend/config/api_urls.py backend/apps/finance/tests/test_finance.py
git commit -m "feat(finance): BillingProfileViewSet (activate/edit/deactivate)"
```

---

### Task 8: API — `DueViewSet` (list, registrar-pagamento, cancelar-pagamento)

**Files:**
- Modify: `backend/apps/finance/api/views.py`
- Modify: `backend/config/api_urls.py`
- Test: `backend/apps/finance/tests/test_finance.py`

**Interfaces:**
- Consumes: `FinanceService.{register_payment, cancel_payment}` (Tasks 3–4),
  `DueSerializer`, `RegisterPaymentSerializer` (Task 7).
- Produces: `DueViewSet`. Router path `dues` (`/api/dues`,
  `/api/dues/registrar-pagamento`, `/api/dues/{id}/cancelar-pagamento`).

- [ ] **Step 1: Write the failing tests**

Append to `backend/apps/finance/tests/test_finance.py`:

```python
def test_registrar_pagamento_via_api(client: APIClient):
    tenant, admin = _org("finapi4")
    with use_tenant(tenant.id):
        member = UserService().create_user(
            username="membro_api4", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "due_day": 10, "started_period": _period_str(0)},
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
    tenant, admin = _org("finapi5")
    with use_tenant(tenant.id):
        member = UserService().create_user(
            username="membro_api5", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(member)
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
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "due_day": 10, "started_period": _period_str(0)},
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


def test_dues_cannot_be_deleted_directly(client: APIClient):
    tenant, admin = _org("finapi7")
    with use_tenant(tenant.id):
        member = UserService().create_user(
            username="membro_api7", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )
    due = client.get(f"/api/dues?user={member.id}").data["results"][0]
    assert client.delete(f"/api/dues/{due['id']}").status_code == 405
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -k "pagamento or dues_cannot" -v`
Expected: FAIL — `404` (routes don't exist yet).

- [ ] **Step 3: Write `DueViewSet`**

In `backend/apps/finance/api/views.py`, change the import block from:

```python
from ..models import BillingProfile
from ..services import FinanceService
from .serializers import ActivateBillingSerializer, BillingProfileSerializer, UpdateDueDaySerializer
```

to:

```python
from ..models import BillingProfile, Due
from ..services import FinanceService
from .serializers import (
    ActivateBillingSerializer,
    BillingProfileSerializer,
    DueSerializer,
    RegisterPaymentSerializer,
    UpdateDueDaySerializer,
)
```

Then append, at the end of the file:

```python


class DueViewSet(TenantScopedViewSet):
    serializer_class = DueSerializer
    queryset = Due.objects.none()
    service = FinanceService()
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):  # type: ignore[override]
        if not _can_read(self.request.user):
            raise BusinessRuleError("Sem permissão para ver o financeiro.", code="forbidden")
        qs = self.service.dues.all().select_related("billing_profile__user")
        profile = self.request.query_params.get("billing_profile")
        user = self.request.query_params.get("user")
        status_f = self.request.query_params.get("status")
        if profile:
            qs = qs.filter(billing_profile_id=profile)
        if user:
            qs = qs.filter(billing_profile__user_id=user)
        if status_f:
            qs = qs.filter(status=status_f)
        return qs.order_by("period")

    @extend_schema(request=RegisterPaymentSerializer, responses={200: DueSerializer(many=True)})
    @action(detail=False, methods=["post"], url_path="registrar-pagamento")
    def registrar_pagamento(self, request: Request) -> Response:
        if not _can_manage(request.user):
            raise BusinessRuleError("Apenas Administrador registra pagamento.", code="forbidden")
        payload = RegisterPaymentSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        dues = self.service.register_payment(
            user=payload.validated_data["user"],
            amount=payload.validated_data["amount"],
            method=payload.validated_data["method"],
            paid_at=payload.validated_data["paid_at"],
            actor_id=str(request.user.pk),
        )
        return Response(DueSerializer(dues, many=True).data)

    @extend_schema(responses={200: DueSerializer(many=True)})
    @action(detail=True, methods=["post"], url_path="cancelar-pagamento")
    def cancelar_pagamento(self, request: Request, pk: str = "") -> Response:
        if not _can_manage(request.user):
            raise BusinessRuleError("Apenas Administrador cancela pagamento.", code="forbidden")
        dues = self.service.cancel_payment(due_id=pk, actor_id=str(request.user.pk))
        return Response(DueSerializer(dues, many=True).data)
```

- [ ] **Step 4: Register the route**

In `backend/config/api_urls.py`, change the finance import from:

```python
from apps.finance.api.views import BillingProfileViewSet
```

to:

```python
from apps.finance.api.views import BillingProfileViewSet, DueViewSet
```

And add the registration:

```python
router.register("dues", DueViewSet, basename="due")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full backend suite**

Run: `docker compose exec backend pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/apps/finance/api/views.py backend/config/api_urls.py backend/apps/finance/tests/test_finance.py
git commit -m "feat(finance): DueViewSet (list, registrar/cancelar pagamento)"
```

---

### Task 9: API — dashboard and `/finance/me`

**Files:**
- Modify: `backend/apps/finance/api/views.py`
- Modify: `backend/config/api_urls.py`
- Test: `backend/apps/finance/tests/test_finance.py`

**Interfaces:**
- Consumes: `FinanceService.{dashboard, summary_for}` (Task 6).
- Produces: `FinanceDashboardView`, `MyFinanceView`. Routes
  `GET /api/finance/dashboard`, `GET /api/finance/me`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/apps/finance/tests/test_finance.py`:

```python
def test_finance_dashboard_requires_staff_read(client: APIClient):
    tenant, admin = _org("finapi8")
    with use_tenant(tenant.id):
        plain = UserService().create_user(
            username="plain_fin8", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
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
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
        not_billed = UserService().create_user(
            username="membro_api9b", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    client.post(
        "/api/billing-profiles",
        {"user": str(member.id), "due_day": 10, "started_period": _period_str(0)},
        format="json",
    )

    client.force_authenticate(member)
    resp = client.get("/api/finance/me")
    assert resp.status_code == 200, resp.data
    assert "financial_status" in resp.data

    client.force_authenticate(not_billed)
    assert client.get("/api/finance/me").status_code == 404
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -k "finance_dashboard or finance_me" -v`
Expected: FAIL — `404` (routes don't exist yet).

- [ ] **Step 3: Write the two views**

In `backend/apps/finance/api/views.py`, change the import block at the top
from:

```python
"""Financeiro HTTP layer. Regras no FinanceService; sem lógica aqui."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import RoleCode
from core.exceptions import BusinessRuleError
from core.viewsets import TenantScopedViewSet
```

to:

```python
"""Financeiro HTTP layer. Regras no FinanceService; sem lógica aqui."""
from __future__ import annotations

from datetime import datetime

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import RoleCode
from core.exceptions import BusinessRuleError
from core.viewsets import TenantContextAPIView, TenantScopedViewSet
```

Then append, at the end of the file:

```python


class FinanceDashboardView(TenantContextAPIView):
    """Indicadores agregados do financeiro, para o painel do admin."""

    permission_classes = [IsAuthenticated]
    service = FinanceService()

    def get(self, request: Request) -> Response:
        if not _can_read(request.user):
            raise BusinessRuleError("Sem permissão para ver o financeiro.", code="forbidden")
        raw_from = request.query_params.get("from")
        raw_to = request.query_params.get("to")
        date_from = datetime.strptime(raw_from, "%Y-%m-%d").date() if raw_from else None
        date_to = datetime.strptime(raw_to, "%Y-%m-%d").date() if raw_to else None
        return Response(self.service.dashboard(date_from=date_from, date_to=date_to))


class MyFinanceView(TenantContextAPIView):
    """Situação financeira de quem está logado."""

    permission_classes = [IsAuthenticated]
    service = FinanceService()

    def get(self, request: Request) -> Response:
        profile = self.service.profiles.profile_for_user(request.user.pk)
        if profile is None or not profile.is_active:
            return Response(status=404)
        return Response(self.service.summary_for(profile))
```

- [ ] **Step 4: Register the routes**

In `backend/config/api_urls.py`, change the finance import from:

```python
from apps.finance.api.views import BillingProfileViewSet, DueViewSet
```

to:

```python
from apps.finance.api.views import (
    BillingProfileViewSet,
    DueViewSet,
    FinanceDashboardView,
    MyFinanceView,
)
```

And add these two standalone paths alongside the other `path(...)` entries
(near `path("credits", ...)`):

```python
    path("finance/dashboard", FinanceDashboardView.as_view(), name="finance_dashboard"),
    path("finance/me", MyFinanceView.as_view(), name="finance_me"),
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `docker compose exec backend pytest apps/finance/tests/test_finance.py -v`
Expected: PASS (every test in the file — this is the last backend task).

- [ ] **Step 6: Run the full backend suite**

Run: `docker compose exec backend pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/apps/finance/api/views.py backend/config/api_urls.py backend/apps/finance/tests/test_finance.py
git commit -m "feat(finance): dashboard and /finance/me endpoints"
```

---

### Task 10: Frontend — `features/finance/api.ts` and module wiring

**Files:**
- Create: `frontend/src/features/finance/api.ts`
- Modify: `frontend/src/modules.ts:29-31`

**Interfaces:**
- Produces: `useFinanceDashboard`, `useBillingProfiles`, `useActivateBilling`,
  `useUpdateDueDay`, `useDeactivateBilling`, `useDues`,
  `useRegisterPayment`, `useCancelPayment`, `useMyFinance` hooks, plus
  `BillingProfile`, `Due`, `FinanceDashboard`, `MyFinanceSummary` TS
  interfaces, and `FINANCIAL_STATUS_LABEL`/`FINANCIAL_STATUS_BADGE` maps
  (consumed by Tasks 11–13).

- [ ] **Step 1: Flip the module on**

In `frontend/src/modules.ts`, change:

```ts
  {
    id: "financeiro",
    name: "Sistema Financeiro",
    summary: "Mensalidades, caixa e prestação de contas do grêmio.",
    to: "/financeiro",
    available: false,
    roles: ["admin", "director", "inventory", "auditor"],
  },
```

to:

```ts
  {
    id: "financeiro",
    name: "Sistema Financeiro",
    summary: "Mensalidades, caixa e prestação de contas do grêmio.",
    to: "/financeiro",
    available: true,
    roles: ["admin", "director", "inventory", "auditor"],
  },
```

- [ ] **Step 2: Write the API hooks**

Create `frontend/src/features/finance/api.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";

export type FinancialStatus =
  | "up_to_date"
  | "paid_in_advance"
  | "due_soon"
  | "due_today"
  | "overdue"
  | "delinquent";

export const FINANCIAL_STATUS_LABEL: Record<FinancialStatus, string> = {
  up_to_date: "Em dia",
  paid_in_advance: "Pago antecipadamente",
  due_soon: "Próximo do vencimento",
  due_today: "Vencendo hoje",
  overdue: "Vencido",
  delinquent: "Inadimplente",
};

/** Classe de badge (Tabler) por situação — verde a vermelho conforme piora. */
export const FINANCIAL_STATUS_BADGE: Record<FinancialStatus, string> = {
  up_to_date: "bg-green-lt",
  paid_in_advance: "bg-blue-lt",
  due_soon: "bg-yellow-lt",
  due_today: "bg-orange-lt",
  overdue: "bg-red-lt",
  delinquent: "bg-red-lt",
};

export interface BillingProfile {
  id: string;
  user: string;
  user_name: string;
  user_posto: string;
  due_day: number;
  started_period: string;
  is_active: boolean;
  financial_status: FinancialStatus;
  financial_status_label: string;
  last_payment_at: string | null;
}

export type DueStatus =
  | "pending"
  | "due_soon"
  | "due_today"
  | "overdue"
  | "delinquent"
  | "paid";

export interface Due {
  id: string;
  billing_profile: string;
  user: string;
  user_name: string;
  period: string;
  due_date: string;
  amount: string;
  status: DueStatus;
  status_label: string;
  paid_in_advance: boolean;
  paid_at: string | null;
}

interface Paginated<T> {
  results: T[];
  count: number;
}

export function useBillingProfiles() {
  return useQuery({
    queryKey: ["finance", "billing-profiles"],
    queryFn: async () =>
      (await api.get<Paginated<BillingProfile>>("/billing-profiles?page_size=200")).data.results,
  });
}

export interface ActivateBillingPayload {
  user: string;
  due_day: number;
  started_period: string;
}

export function useActivateBilling() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ActivateBillingPayload) =>
      (await api.post<BillingProfile>("/billing-profiles", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

export function useUpdateDueDay() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, due_day }: { id: string; due_day: number }) =>
      (await api.patch<BillingProfile>(`/billing-profiles/${id}`, { due_day })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

export function useDeactivateBilling() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      (await api.post<BillingProfile>(`/billing-profiles/${id}/desativar`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

export function useDues(filters: { billing_profile?: string; user?: string; status?: string }) {
  const { billing_profile, user, status } = filters;
  return useQuery({
    queryKey: ["finance", "dues", { billing_profile, user, status }],
    enabled: !!(billing_profile || user),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (billing_profile) params.set("billing_profile", billing_profile);
      if (user) params.set("user", user);
      if (status) params.set("status", status);
      params.set("page_size", "200");
      return (await api.get<Paginated<Due>>(`/dues?${params.toString()}`)).data.results;
    },
  });
}

export interface RegisterPaymentPayload {
  user: string;
  amount: string;
  method: "dinheiro" | "transferencia" | "pix";
  paid_at: string;
}

export function useRegisterPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: RegisterPaymentPayload) =>
      (await api.post<Due[]>("/dues/registrar-pagamento", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

export function useCancelPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (dueId: string) =>
      (await api.post<Due[]>(`/dues/${dueId}/cancelar-pagamento`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

export interface FinanceDashboard {
  total_users: number;
  up_to_date_count: number;
  paid_in_advance_count: number;
  due_soon_count: number;
  due_today_count: number;
  overdue_count: number;
  delinquent_count: number;
  dues_upcoming_30_days: number;
  dues_overdue: number;
  payments_received: string;
  pending_amount: string;
  advance_payments_received: string;
  upcoming_receivable: string;
}

export function useFinanceDashboard() {
  return useQuery({
    queryKey: ["finance", "dashboard"],
    queryFn: async () => (await api.get<FinanceDashboard>("/finance/dashboard")).data,
  });
}

export interface MyFinanceSummary {
  financial_status: FinancialStatus;
  due_day: number;
  next_due_date: string | null;
  days_until_due: number | null;
  days_overdue: number;
  months_paid: number;
  months_paid_in_advance: number;
  months_open: number;
  pending_amount: string;
  last_payment_at: string | null;
  paid_through_period: string | null;
}

/** 404 = usuário não está na relação financeira (Sd/Cb ou nunca ativado). */
export function useMyFinance() {
  return useQuery({
    queryKey: ["finance", "me"],
    queryFn: async () => {
      try {
        return (await api.get<MyFinanceSummary>("/finance/me")).data;
      } catch (err) {
        const status = (err as { response?: { status?: number } }).response?.status;
        if (status === 404) return null;
        throw err;
      }
    },
  });
}
```

- [ ] **Step 2: Verify with lint/typecheck**

Run: `docker compose exec frontend npm run lint`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/finance/api.ts frontend/src/modules.ts
git commit -m "feat(frontend): finance API hooks, enable Financeiro module"
```

---

### Task 11: Frontend — `FinancePage.tsx` (dashboard + table + ativar)

**Files:**
- Modify: `frontend/src/pages/FinancePage.tsx` (full rewrite)

**Interfaces:**
- Consumes: everything from Task 10.

- [ ] **Step 1: Rewrite `FinancePage.tsx`**

Replace the entire content of `frontend/src/pages/FinancePage.tsx` with:

```tsx
import { IconBuildingBank, IconPlus } from "@tabler/icons-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { brl } from "../features/barbershop/api";
import {
  FINANCIAL_STATUS_BADGE,
  FINANCIAL_STATUS_LABEL,
  useActivateBilling,
  useBillingProfiles,
  useFinanceDashboard,
  type BillingProfile,
} from "../features/finance/api";
import { useUsers } from "../features/accounts/api";

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="col-sm-6 col-lg-3">
      <div className="card card-sm">
        <div className="card-body">
          <div className="text-secondary small">{label}</div>
          <div className="h2 mb-0">{value}</div>
        </div>
      </div>
    </div>
  );
}

function ActivateBillingModal({ onClose }: { onClose: () => void }) {
  const { data: users } = useUsers();
  const { data: profiles } = useBillingProfiles();
  const activate = useActivateBilling();
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({ user: "", due_day: 10, started_period: today.slice(0, 8) + "01" });
  const [error, setError] = useState<string | null>(null);

  // Quem já está na relação (ativa ou não) não aparece de novo — reativar
  // exige editar o cadastro existente, não criar um segundo.
  const billedIds = new Set((profiles ?? []).map((p) => p.user));
  const candidatos = (users ?? []).filter(
    (u) => u.posto_graduacao !== "Sd" && u.posto_graduacao !== "Cb" && !billedIds.has(u.id),
  );

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await activate.mutateAsync(form);
      onClose();
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response?.data
        ?.error?.message;
      setError(msg ?? "Não foi possível ativar a cobrança.");
    }
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Ativar cobrança</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                {error && <div className="alert alert-danger">{error}</div>}
                <div className="mb-3">
                  <label className="form-label required">Usuário</label>
                  <select
                    className="form-select"
                    value={form.user}
                    onChange={(e) => setForm((f) => ({ ...f, user: e.target.value }))}
                    required
                  >
                    <option value="">Selecione…</option>
                    {candidatos.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.display_name || u.username}
                      </option>
                    ))}
                  </select>
                  <div className="form-hint">Praças (Sd/Cb) não aparecem — não entram na relação.</div>
                </div>
                <div className="row">
                  <div className="col-6 mb-3">
                    <label className="form-label required">Dia de vencimento</label>
                    <input
                      type="number"
                      className="form-control"
                      min={1}
                      max={31}
                      value={form.due_day}
                      onChange={(e) => setForm((f) => ({ ...f, due_day: Number(e.target.value) }))}
                      required
                    />
                  </div>
                  <div className="col-6 mb-3">
                    <label className="form-label required">Mês de início</label>
                    <input
                      type="date"
                      className="form-control"
                      value={form.started_period}
                      onChange={(e) => setForm((f) => ({ ...f, started_period: e.target.value }))}
                      required
                    />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={activate.isPending}>
                  {activate.isPending ? "Ativando…" : "Ativar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
      <div className="modal-backdrop fade show" />
    </>
  );
}

export default function FinancePage() {
  const { data: dashboard } = useFinanceDashboard();
  const { data: profiles, isLoading } = useBillingProfiles();
  const [activating, setActivating] = useState(false);

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <div className="page-pretitle">Módulo</div>
            <h2 className="page-title">
              <IconBuildingBank size={22} className="me-2" />
              Sistema Financeiro
            </h2>
          </div>
          <div className="col-auto">
            <button className="btn btn-primary" onClick={() => setActivating(true)}>
              <IconPlus size={18} className="me-1" />
              Ativar cobrança
            </button>
          </div>
        </div>
      </div>

      {dashboard && (
        <div className="row row-cards mt-3 g-3">
          <StatCard label="Usuários na relação" value={dashboard.total_users} />
          <StatCard label="Em dia" value={dashboard.up_to_date_count} />
          <StatCard label="Inadimplentes" value={dashboard.delinquent_count} />
          <StatCard label="Vencidas" value={dashboard.dues_overdue} />
          <StatCard label="A vencer (30 dias)" value={dashboard.dues_upcoming_30_days} />
          <StatCard label="Valores em aberto" value={`R$ ${brl(dashboard.pending_amount)}`} />
          <StatCard label="Recebido antecipado" value={`R$ ${brl(dashboard.advance_payments_received)}`} />
          <StatCard label="Previsão a receber" value={`R$ ${brl(dashboard.upcoming_receivable)}`} />
        </div>
      )}

      <div className="card mt-3">
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th>Usuário</th>
                <th>Posto/Grad.</th>
                <th>Situação</th>
                <th>Vencimento</th>
                <th className="w-1" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={5} className="text-secondary">Carregando…</td>
                </tr>
              )}
              {!isLoading && (profiles ?? []).length === 0 && (
                <tr>
                  <td colSpan={5} className="text-secondary text-center py-4">
                    Nenhum usuário na relação financeira ainda.
                  </td>
                </tr>
              )}
              {(profiles ?? []).map((p: BillingProfile) => (
                <tr key={p.id}>
                  <td>{p.user_name}</td>
                  <td>{p.user_posto || "—"}</td>
                  <td>
                    <span className={`badge ${FINANCIAL_STATUS_BADGE[p.financial_status]}`}>
                      {FINANCIAL_STATUS_LABEL[p.financial_status]}
                    </span>
                    {!p.is_active && <span className="badge bg-secondary-lt ms-1">Desativado</span>}
                  </td>
                  <td>Dia {p.due_day}</td>
                  <td>
                    <Link to={`/financeiro/${p.id}`} className="btn btn-sm btn-ghost-secondary">
                      Ver extrato
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {activating && <ActivateBillingModal onClose={() => setActivating(false)} />}
    </>
  );
}
```

- [ ] **Step 2: Verify with lint/typecheck**

Run: `docker compose exec frontend npm run lint`
Expected: no errors (fix the unused import per the note above if it appears).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/FinancePage.tsx
git commit -m "feat(frontend): Financeiro dashboard, table, and activation modal"
```

---

### Task 12: Frontend — extrato page + registrar pagamento modal

**Files:**
- Create: `frontend/src/pages/FinanceStatementPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `useDues`, `useRegisterPayment`, `useCancelPayment`,
  `useBillingProfiles`, `useDeactivateBilling` (Task 10).

- [ ] **Step 1: Write the statement page**

Create `frontend/src/pages/FinanceStatementPage.tsx`:

```tsx
import { IconArrowLeft, IconCash } from "@tabler/icons-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { brl } from "../features/barbershop/api";
import {
  FINANCIAL_STATUS_BADGE,
  useBillingProfiles,
  useCancelPayment,
  useDeactivateBilling,
  useDues,
  useRegisterPayment,
  type RegisterPaymentPayload,
} from "../features/finance/api";

function periodLabel(iso: string): string {
  const [year, month] = iso.split("-");
  return new Date(Number(year), Number(month) - 1, 1).toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
  });
}

function RegisterPaymentModal({
  userId,
  feeHint,
  onClose,
}: {
  userId: string;
  /** Valor de uma mensalidade, pra pré-visualizar quantos meses o pagamento cobre.
   *  Vem da própria Due mais recente do usuário — nunca hardcoded (MEMBERSHIP_FEE
   *  pode mudar; a Due já gerada carrega o valor real daquele mês). */
  feeHint: number;
  onClose: () => void;
}) {
  const register = useRegisterPayment();
  const [form, setForm] = useState<RegisterPaymentPayload>({
    user: userId,
    amount: "",
    method: "dinheiro",
    paid_at: new Date().toISOString().slice(0, 16),
  });
  const [error, setError] = useState<string | null>(null);

  const meses =
    Number(form.amount) > 0 && feeHint > 0 ? Math.floor(Number(form.amount) / feeHint) : 0;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await register.mutateAsync({ ...form, paid_at: new Date(form.paid_at).toISOString() });
      onClose();
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response?.data
        ?.error?.message;
      setError(msg ?? "Não foi possível registrar o pagamento.");
    }
  }

  return (
    <>
      <div className="modal modal-blur show d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Registrar pagamento</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <form onSubmit={submit}>
              <div className="modal-body">
                {error && <div className="alert alert-danger">{error}</div>}
                <div className="row">
                  <div className="col-6 mb-3">
                    <label className="form-label required">Valor</label>
                    <input
                      type="number"
                      step="0.01"
                      className="form-control"
                      value={form.amount}
                      onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
                      required
                    />
                  </div>
                  <div className="col-6 mb-3">
                    <label className="form-label required">Forma</label>
                    <select
                      className="form-select"
                      value={form.method}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, method: e.target.value as RegisterPaymentPayload["method"] }))
                      }
                    >
                      <option value="dinheiro">Dinheiro</option>
                      <option value="transferencia">Transferência</option>
                      <option value="pix">Pix (manual)</option>
                    </select>
                  </div>
                </div>
                <div className="mb-3">
                  <label className="form-label required">Data do pagamento</label>
                  <input
                    type="datetime-local"
                    className="form-control"
                    value={form.paid_at}
                    onChange={(e) => setForm((f) => ({ ...f, paid_at: e.target.value }))}
                    required
                  />
                </div>
                {meses > 0 && (
                  <div className="alert alert-info mb-0">
                    Esse valor cobre {meses} {meses === 1 ? "mês" : "meses"} de mensalidade.
                  </div>
                )}
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-link" onClick={onClose}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={register.isPending}>
                  {register.isPending ? "Registrando…" : "Registrar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
      <div className="modal-backdrop fade show" />
    </>
  );
}

export default function FinanceStatementPage() {
  const { id = "" } = useParams();
  const { data: profiles } = useBillingProfiles();
  const profile = (profiles ?? []).find((p) => p.id === id);
  const { data: dues, isLoading } = useDues({ billing_profile: id });
  const cancel = useCancelPayment();
  const deactivate = useDeactivateBilling();
  const [registering, setRegistering] = useState(false);

  if (!profile) return null;

  return (
    <>
      <div className="page-header">
        <div className="row align-items-center">
          <div className="col">
            <Link to="/financeiro" className="text-secondary text-decoration-none small mb-1 d-block">
              <IconArrowLeft size={14} className="me-1" />
              Financeiro
            </Link>
            <h2 className="page-title">{profile.user_name}</h2>
            <div className="text-secondary mt-1">
              <span className={`badge ${FINANCIAL_STATUS_BADGE[profile.financial_status]}`}>
                {profile.financial_status_label}
              </span>
            </div>
          </div>
          <div className="col-auto d-flex gap-2">
            {profile.is_active && (
              <button
                className="btn btn-outline-danger"
                onClick={() => {
                  if (confirm(`Desativar a cobrança de ${profile.user_name}?`)) deactivate.mutate(profile.id);
                }}
              >
                Desativar cobrança
              </button>
            )}
            <button className="btn btn-primary" onClick={() => setRegistering(true)}>
              <IconCash size={18} className="me-1" />
              Registrar pagamento
            </button>
          </div>
        </div>
      </div>

      <div className="card mt-3">
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th>Período</th>
                <th>Vencimento</th>
                <th>Valor</th>
                <th>Situação</th>
                <th className="w-1" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={5} className="text-secondary">Carregando…</td>
                </tr>
              )}
              {(dues ?? []).map((due) => (
                <tr key={due.id}>
                  <td className="text-capitalize">{periodLabel(due.period)}</td>
                  <td>{formatDateBr(due.due_date)}</td>
                  <td>R$ {brl(due.amount)}</td>
                  <td>
                    {due.status_label}
                    {due.paid_in_advance && (
                      <span className="badge bg-blue-lt ms-1">Antecipado</span>
                    )}
                  </td>
                  <td>
                    {due.status === "paid" && (
                      <button
                        className="btn btn-sm btn-ghost-danger"
                        onClick={() => {
                          if (confirm("Cancelar este pagamento? A mensalidade volta a ficar em aberto."))
                            cancel.mutate(due.id);
                        }}
                      >
                        Cancelar pagamento
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {registering && (
        <RegisterPaymentModal
          userId={profile.user}
          feeHint={Number((dues ?? []).at(-1)?.amount ?? 0)}
          onClose={() => setRegistering(false)}
        />
      )}
    </>
  );
}
```

- [ ] **Step 2: Add the route**

In `frontend/src/App.tsx`, change:

```tsx
          <Route element={<RequireRole roles={STAFF_ROLES} />}>
            <Route path="financeiro" element={<FinancePage />} />
          </Route>
```

to:

```tsx
          <Route element={<RequireRole roles={STAFF_ROLES} />}>
            <Route path="financeiro" element={<FinancePage />} />
            <Route path="financeiro/:id" element={<FinanceStatementPage />} />
          </Route>
```

And add the import (alongside the other `import X from "./pages/X"` lines):

```tsx
import FinanceStatementPage from "./pages/FinanceStatementPage";
```

- [ ] **Step 3: Verify with lint/typecheck**

Run: `docker compose exec frontend npm run lint`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/FinanceStatementPage.tsx frontend/src/App.tsx
git commit -m "feat(frontend): per-user finance statement and payment registration"
```

---

### Task 13: Frontend — "Minha mensalidade" card on `ProfilePage.tsx`

**Files:**
- Modify: `frontend/src/pages/ProfilePage.tsx`

**Interfaces:**
- Consumes: `useMyFinance` (Task 10).

- [ ] **Step 1: Add the card**

In `frontend/src/pages/ProfilePage.tsx`, add the import (alongside the other
feature imports near the top):

```tsx
import {
  FINANCIAL_STATUS_BADGE,
  FINANCIAL_STATUS_LABEL,
  useMyFinance,
} from "../features/finance/api";
```

Add `IconReceipt2` to the existing `@tabler/icons-react` import line
(currently `import { IconLock, IconUser, IconWallet } from
"@tabler/icons-react";`):

```tsx
import { IconLock, IconReceipt2, IconUser, IconWallet } from "@tabler/icons-react";
```

Add this component right after the existing `CreditCard` function (before
`export default function ProfilePage()`):

```tsx
/** Situação da mensalidade — só aparece pra quem está na relação financeira. */
function FinanceCard() {
  const { data, isLoading } = useMyFinance();
  if (isLoading || !data) return null;

  return (
    <div className="card mt-3">
      <div className="card-header d-flex align-items-center gap-2">
        <IconReceipt2 size={20} />
        <h3 className="card-title m-0">Minha mensalidade</h3>
        <span className={`badge ms-auto ${FINANCIAL_STATUS_BADGE[data.financial_status]}`}>
          {FINANCIAL_STATUS_LABEL[data.financial_status]}
        </span>
      </div>
      <div className="card-body">
        <div className="datagrid">
          <div className="datagrid-item">
            <div className="datagrid-title">Próximo vencimento</div>
            <div className="datagrid-content">
              {data.next_due_date ? formatDateBr(data.next_due_date) : "—"}
            </div>
          </div>
          <div className="datagrid-item">
            <div className="datagrid-title">Meses pagos</div>
            <div className="datagrid-content">{data.months_paid}</div>
          </div>
          <div className="datagrid-item">
            <div className="datagrid-title">Meses em aberto</div>
            <div className="datagrid-content">{data.months_open}</div>
          </div>
          <div className="datagrid-item">
            <div className="datagrid-title">Valor pendente</div>
            <div className="datagrid-content">R$ {brl(data.pending_amount)}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

Then in `export default function ProfilePage()`, add `<FinanceCard />` right
after `<CreditCard />`:

```tsx
      <CreditCard />
      <FinanceCard />
```

- [ ] **Step 2: Verify with lint/typecheck**

Run: `docker compose exec frontend npm run lint`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProfilePage.tsx
git commit -m "feat(frontend): Minha mensalidade card on the profile page"
```

---

### Task 14: End-to-end manual verification

**Files:** none — verification only. The stack is already running via
`docker compose up`.

- [ ] **Step 1: Create a throwaway admin and a throwaway member for testing**

Do **not** touch real accounts (there are real users in this tenant,
including the project owner's own login). Create disposable test users the
same way Task 6 of the previous plan did:

```bash
docker compose exec backend python manage.py shell -c "
from apps.accounts.models import RoleCode, User
from apps.accounts.services import UserService
from core.context import use_tenant
tenant_id = User.objects.filter(roles__code=RoleCode.ADMIN).first().tenant_id
with use_tenant(tenant_id):
    UserService().create_user(
        username='qa.finance.member@example.com', password='supersecret123',
        email='qa.finance.member@example.com', full_name='QA Finance Member',
        role_codes=[RoleCode.USER], tenant_id=tenant_id,
    )
print('created')
"
```

- [ ] **Step 2: Log in as an existing admin, open Financeiro**

At `http://localhost:5173/login`, sign in as an admin. Navigate to
`/financeiro`. Expected: dashboard cards render (all zero/low, this is a
fresh module), table shows "Nenhum usuário na relação financeira ainda."

- [ ] **Step 3: Activate billing for the QA member**

Click "Ativar cobrança", pick `qa.finance.member@example.com`, due day 10,
start month = current month. Confirm the request-body's start-of-month
matches what you typed (frontend truncates the date input to day 01).
Expected: modal closes, the user now appears in the table with situação "Em
dia" (or "Próximo do vencimento"/"Vencido" depending on today's date vs. day
10 — either is correct, just confirm it's not stuck loading or erroring).

- [ ] **Step 4: Open the extrato, register a payment**

Click "Ver extrato". Expected: 3 rows (current month + 2 ahead), all
pending/open. Click "Registrar pagamento", enter an amount equal to 2× the
configured `MEMBERSHIP_FEE` (check `backend/.env` for the actual value —
default 100.00, so enter 200.00), method "Dinheiro", today's date/time.
Expected: after submit, the two oldest rows show "Pago", the table's
dashboard numbers update when you go back to `/financeiro`.

- [ ] **Step 5: Cancel a payment**

Still on the extrato, click "Cancelar pagamento" on one of the rows just
paid. Expected: it reverts to its time-based status (Pendente/Próximo do
vencimento/etc.), not stuck as "Pago".

- [ ] **Step 6: Check the self-service card**

Log out, log in as `qa.finance.member@example.com` (password
`supersecret123`). Go to `/perfil`. Expected: a "Minha mensalidade" card
appears below "Meu crédito", showing the current situação, next due date,
months paid/open.

- [ ] **Step 7: Check Sd/Cb exclusion**

Log back in as admin. In Usuários, create or edit a user to posto "Sd" (or
reuse one from earlier work). Go to Financeiro → Ativar cobrança: confirm
that user does **not** appear in the dropdown.

- [ ] **Step 8: Clean up**

```bash
docker compose exec backend python manage.py shell -c "
from apps.accounts.models import User
u = User.objects.filter(username='qa.finance.member@example.com').first()
if u:
    u.is_active = False
    u.save(update_fields=['is_active'])
    print('deactivated (has billing/payment history, cannot hard-delete)')
"
```

No commit for this task — if any step fails, go back to the relevant
earlier task and fix it before considering the plan done.
