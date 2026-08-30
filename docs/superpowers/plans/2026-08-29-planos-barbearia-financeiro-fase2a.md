# Planos da Barbearia e Financeiro — Fase 2a (núcleo) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir a mensalidade única do Financeiro por dois planos
(Associado R$30, Mensalista Barbearia R$20) com elegibilidade por posto,
abrir a relação financeira pra todo mundo (fim da exclusão de Cb/Sd),
introduzir o convite do Associado e o autoatendimento de assinatura, e
preparar o cadastro de postos (Sd → Sd EP/Sd EV) que a elegibilidade
depende.

**Architecture:** Tudo dentro de `apps.accounts` (postos) e `apps.finance`
(planos, elegibilidade, convite, autoatendimento) + frontend correspondente.
Reaproveita 100% da mecânica de ledger já existente (`Due`, `Payment`,
`FinanceCredit`) — só troca a origem do valor cobrado. Não toca
`apps.barbershop` nesta fase (a integração de cota mensal com a Agenda é a
Fase 2b, um plano separado, que depende deste).

**Tech Stack:** Django + DRF (backend), React + TS + Vite (frontend),
PostgreSQL, pytest-django.

## Global Constraints

- `PlanCode.ASSOCIADO` = R$ 30,00 (`settings.ASSOCIADO_FEE`, padrão
  `"30.00"`), `PlanCode.BARBEARIA` = R$ 20,00 (`settings.BARBEARIA_FEE`,
  padrão `"20.00"`) — mesmo padrão de leitura tardia de `MEMBERSHIP_FEE`
  atual (nunca importado no módulo, lido a cada chamada).
- Convite do Associado expira em `settings.ASSOCIADO_INVITE_DAYS` dias
  (padrão `7`).
- Matriz de elegibilidade (constantes em `apps/finance/models.py`):
  - `"Sd EV"` → só `BARBEARIA`.
  - `"Sd EP"`, `"Cb"` → `ASSOCIADO` e `BARBEARIA`.
  - `""` (vazio) e `"Sd"` (posto legado, ainda não reclassificado) → nenhum
    plano.
  - Qualquer outro posto (graduado/oficial) → só `ASSOCIADO`.
- O convite do Associado é uma facilidade de autoatendimento, **não** uma
  trava sobre o Administrador: o admin continua podendo ativar qualquer
  plano elegível diretamente pela tela de "Ativar cobrança", com ou sem
  convite. O convite só importa pra quando é o **próprio usuário** que
  ativa.
- `BillingProfile.plan` é obrigatório em toda ativação (nova ou
  reativação) — sem valor default implícito.
- `Due.amount` continua congelado no ato de criação (preço da mensalidade
  já gerada nunca muda retroativamente) — princípio já usado em toda a
  base, não mexe nisso.
- Todo teste de data usa os helpers relativos já existentes em
  `test_finance.py` (`_period`, `_period_str`, `_dt`, `_dt_str`) — nunca
  data de calendário travada.
- Migrações: nunca editar uma já aplicada — sempre uma nova. O campo
  `BillingProfile.plan` entra em 3 passos (nullable → backfill de dados →
  `NOT NULL`), pattern seguro pra campo obrigatório numa tabela já
  povoada.

---

### Task 1: Postos — Sd vira Sd EP e Sd EV

**Files:**
- Modify: `frontend/src/features/accounts/api.ts:181-182`
- Modify: `backend/apps/accounts/models.py:26`
- Modify: `backend/apps/accounts/tests/test_auth_and_rbac.py` (linhas 59,
  119, 146, 376, 432, 529, 552 — literal `"Sd"` em contexto de
  posto_graduacao)
- Modify: `backend/apps/accounts/management/commands/seed_demo.py:44`

**Interfaces:**
- Produz: `BARBERSHOP_ONLY_RANKS = frozenset({"Sd EP", "Sd EV", "Cb"})` em
  `apps/accounts/models.py` — mesma constante, novo conteúdo. Todo código
  que já importa `BARBERSHOP_ONLY_RANKS` (a regra de forçar o perfil
  "Cliente da Barbearia" em `apps/accounts/services.py:44`) não muda uma
  linha — só o conteúdo da constante muda.

- [ ] **Step 1: Trocar "Sd" por "Sd EP"/"Sd EV" na lista de postos do frontend**

Em `frontend/src/features/accounts/api.ts`, dentro do grupo `"Praças"` de
`MILITARY_RANKS` (linhas 175-184), troque:

```typescript
      { value: "Cb", label: "Cabo" },
      { value: "Sd", label: "Soldado" },
```

por:

```typescript
      { value: "Cb", label: "Cabo" },
      { value: "Sd EP", label: "Soldado EP" },
      { value: "Sd EV", label: "Soldado EV" },
```

Essa é a ÚNICA lista de postos do frontend (usada por `SignupPage.tsx`,
`ProfilePage.tsx`, `UsersPage.tsx`, `AgendaPage.tsx`) — a mudança propaga
sozinha pra todo formulário de cadastro/edição.

- [ ] **Step 2: Atualizar `BARBERSHOP_ONLY_RANKS`**

Em `backend/apps/accounts/models.py:26`, troque:

```python
BARBERSHOP_ONLY_RANKS = frozenset({"Sd", "Cb"})
```

por:

```python
BARBERSHOP_ONLY_RANKS = frozenset({"Sd EP", "Sd EV", "Cb"})
```

- [ ] **Step 3: Atualizar os testes de RBAC que usam "Sd" como posto de praça**

Em `backend/apps/accounts/tests/test_auth_and_rbac.py`, troque toda
ocorrência do literal `"Sd"` usado como `posto_graduacao` (linhas 59, 119,
146, 376, 432, 529, 552 — confirme com
`grep -n '"Sd"' backend/apps/accounts/tests/test_auth_and_rbac.py`, o
número de linha pode ter deslocado um pouco) por `"Sd EP"`. Não mexa nos
testes que usam `"Cb"` — esse posto não mudou.

- [ ] **Step 4: Atualizar o seed de demonstração**

Em `backend/apps/accounts/management/commands/seed_demo.py:44`, troque
`posto_graduacao="Sd"` por `posto_graduacao="Sd EP"`.

- [ ] **Step 5: Rodar a suíte de accounts**

```bash
docker compose exec backend pytest apps/accounts -q
```

Expected: todos passam — a regra de forçar "Cliente da Barbearia" continua
valendo, agora pra "Sd EP"/"Sd EV"/"Cb" em vez de "Sd"/"Cb".

- [ ] **Step 6: `npm run lint` no frontend**

```bash
cd frontend && npm run lint
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/accounts/api.ts backend/apps/accounts/models.py backend/apps/accounts/tests/test_auth_and_rbac.py backend/apps/accounts/management/commands/seed_demo.py
git commit -m "feat(accounts): Sd vira Sd EP e Sd EV no cadastro de postos"
```

---

### Task 2: Modelo de Plano no Financeiro

**Files:**
- Modify: `backend/apps/finance/models.py`
- Create: migração Django (via `makemigrations`) para o campo `plan`
  (3 migrações: adicionar nullable, backfill de dados, tornar `NOT NULL`)
- Create: `backend/apps/finance/tests/test_finance.py` — testes do modelo
  (adicionados ao arquivo existente)
- Modify: `backend/config/settings/base.py`
- Modify: `backend/.env.example`

**Interfaces:**
- Produz: `PlanCode` (TextChoices: `ASSOCIADO`/`BARBEARIA`), `plan_price(code:
  str) -> Decimal`, `eligible_plans_for(posto_graduacao: str) ->
  frozenset[str]`, `BillingProfile.plan: str`. `membership_fee()` **continua
  existindo** nesta task (ainda é usado por `services.py` até a Task 3) —
  não remova ainda.

- [ ] **Step 1: Adicionar `ASSOCIADO_FEE`/`BARBEARIA_FEE`/`ASSOCIADO_INVITE_DAYS` nas settings**

Em `backend/config/settings/base.py`, logo depois da linha 182
(`MEMBERSHIP_FEE = env("MEMBERSHIP_FEE", default="100.00")`), adicione:

```python
ASSOCIADO_FEE = env("ASSOCIADO_FEE", default="30.00")
BARBEARIA_FEE = env("BARBEARIA_FEE", default="20.00")
ASSOCIADO_INVITE_DAYS = env.int("ASSOCIADO_INVITE_DAYS", default=7)
```

Em `backend/.env.example`, logo depois da linha 23
(`MEMBERSHIP_FEE=100.00`), adicione:

```
ASSOCIADO_FEE=30.00
BARBEARIA_FEE=20.00
ASSOCIADO_INVITE_DAYS=7
```

- [ ] **Step 2: `PlanCode`, `plan_price`, `eligible_plans_for` no models.py**

Em `backend/apps/finance/models.py`, logo depois da função
`membership_fee()` (linha 26), adicione:

```python
class PlanCode(models.TextChoices):
    ASSOCIADO = "associado", "Associado"
    BARBEARIA = "barbearia", "Mensalista Barbearia"


def plan_price(code: str) -> Decimal:
    """Valor do plano, de ASSOCIADO_FEE/BARBEARIA_FEE no .env.

    Mesmo padrão de membership_fee(): lido a cada uso, nunca importado —
    mudar o valor não exige mexer no código, e a mensalidade já gerada
    fica congelada (snapshot em Due.amount).
    """
    if code == PlanCode.ASSOCIADO:
        return Decimal(str(settings.ASSOCIADO_FEE))
    if code == PlanCode.BARBEARIA:
        return Decimal(str(settings.BARBEARIA_FEE))
    raise ValueError(f"Plano desconhecido: {code}")


# Postos que já foram promovidos de "Sd" pro par EP/EV, mas ainda não
# tiveram o cadastro corrigido, ficam de fora até alguém reclassificar —
# não dá pra adivinhar qual dos dois planos vale (RN da Fase 2).
_UNCLASSIFIED_RANKS = frozenset({"Sd"})
_BARBEARIA_ONLY_RANKS = frozenset({"Sd EV"})
_BOTH_PLANS_RANKS = frozenset({"Sd EP", "Cb"})


def eligible_plans_for(posto_graduacao: str) -> frozenset[str]:
    """Quais PlanCode um posto pode assinar (RN da Fase 2 — ver spec)."""
    if not posto_graduacao or posto_graduacao in _UNCLASSIFIED_RANKS:
        return frozenset()
    if posto_graduacao in _BARBEARIA_ONLY_RANKS:
        return frozenset({PlanCode.BARBEARIA})
    if posto_graduacao in _BOTH_PLANS_RANKS:
        return frozenset({PlanCode.ASSOCIADO, PlanCode.BARBEARIA})
    return frozenset({PlanCode.ASSOCIADO})
```

- [ ] **Step 3: Campo `plan` em `BillingProfile` (nullable por enquanto)**

Em `backend/apps/finance/models.py`, na classe `BillingProfile` (depois de
`due_day`), adicione:

```python
    plan = models.CharField(max_length=20, choices=PlanCode.choices, null=True, blank=True)
```

- [ ] **Step 4: Gerar a migração de schema (campo nullable)**

```bash
docker compose exec backend python manage.py makemigrations finance
```

Expected: uma migração nova, só com `AddField` de `plan` (nullable). Confira
o arquivo gerado antes de seguir — deve conter só essa operação.

- [ ] **Step 5: Migração de dados — backfill `plan=ASSOCIADO` nos perfis já ativos**

```bash
docker compose exec backend python manage.py makemigrations finance --empty --name backfill_billing_profile_plan
```

Edite o arquivo gerado (`backend/apps/finance/migrations/00XX_backfill_billing_profile_plan.py`)
pra:

```python
from django.db import migrations


def backfill_plan(apps, schema_editor):
    BillingProfile = apps.get_model("finance", "BillingProfile")
    BillingProfile.objects.filter(plan__isnull=True).update(plan="associado")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "00XX_add_plan_field"),  # ajuste pro nome real gerado no Step 4
    ]

    operations = [
        migrations.RunPython(backfill_plan, noop),
    ]
```

Todo `BillingProfile` que já existia antes desta fase estava na relação
única de mensalidade — vira `ASSOCIADO` (era o relacionamento que essas
pessoas já tinham). `Due`s já geradas não mudam de valor — só o campo
`plan` do perfil.

- [ ] **Step 6: Tornar `plan` obrigatório**

Em `models.py`, troque `null=True, blank=True` por nada (campo obrigatório):

```python
    plan = models.CharField(max_length=20, choices=PlanCode.choices)
```

```bash
docker compose exec backend python manage.py makemigrations finance
```

Expected: uma migração `AlterField` tornando `plan` `NOT NULL`. Como o Step
5 já preencheu toda linha existente, isso não falha.

- [ ] **Step 7: Rodar as três migrações**

```bash
docker compose exec backend python manage.py migrate finance
```

- [ ] **Step 8: Testes do modelo/funções puras**

Adicione a `backend/apps/finance/tests/test_finance.py` (perto de
`test_due_date_respects_short_months`, que também testa função pura):

```python
def test_plan_price_reads_from_settings(settings):
    from apps.finance.models import PlanCode, plan_price

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
    from apps.finance.models import eligible_plans_for

    assert eligible_plans_for(posto) == expected


**Desvio de execução:** um teste adicional cogitado aqui
(`BillingProfile.objects.create(...)` sem `plan` deveria levantar erro)
não se sustenta — `CharField` sem `default=` explícito usa `""` como
default implícito do Django em `.create()`, sem checar `choices` (isso só
roda em `full_clean()`, que `.create()` não chama). Não vale a pena
enrijecer isso: `BillingProfile` só nasce de verdade via
`FinanceService.activate_billing()` (Task 3), que sempre passa `plan`
explicitamente — criar direto pelo model bypassa a camada de Service, algo
que a própria arquitetura já proíbe. Sem teste extra pra isso.
```

- [ ] **Step 9: Rodar a suíte de finance**

```bash
docker compose exec backend pytest apps/finance -q
```

Expected: os testes novos passam. Os testes já existentes que chamam
`FinanceService().activate_billing(...)` ou criam `BillingProfile` direto
sem `plan` **vão quebrar aqui** (campo agora obrigatório) — isso é esperado
e é o trabalho da Task 3, não desta. Não conserte esses testes nesta task.

- [ ] **Step 10: Commit**

```bash
git add backend/apps/finance/models.py backend/apps/finance/migrations/ backend/config/settings/base.py backend/.env.example backend/apps/finance/tests/test_finance.py
git commit -m "feat(finance): modelo de Plano (Associado/Mensalista Barbearia) e matriz de elegibilidade"
```

---

### Task 3: Elegibilidade e ativação por plano no FinanceService

**Files:**
- Modify: `backend/apps/finance/services.py`
- Modify: `backend/apps/finance/models.py` (remove `membership_fee()` e o
  settings `MEMBERSHIP_FEE` associado — última chamada é removida aqui)
- Modify: `backend/config/settings/base.py` (remove `MEMBERSHIP_FEE`)
- Modify: `backend/.env.example` (remove `MEMBERSHIP_FEE`)
- Modify: `backend/apps/finance/tests/test_finance.py` (todos os
  ~24 call sites de `activate_billing(` ganham `plan=...`)

**Interfaces:**
- Consome: `PlanCode`, `plan_price`, `eligible_plans_for` (Task 2).
- Produz: `FinanceService.activate_billing(..., plan: str, ...)` —
  assinatura muda (novo parâmetro obrigatório, mantém tudo mais). Toda
  chamada existente em `services.py` e nos testes precisa do novo
  argumento.

- [ ] **Step 1: `_refuse_if_ineligible` vira checagem de plano**

Em `backend/apps/finance/services.py`, troque o método inteiro:

```python
    def _refuse_if_ineligible(self, user: User) -> None:
        if user.posto_graduacao in BARBERSHOP_ONLY_RANKS:
            raise BusinessRuleError(
                "Praças (Sd/Cb) não entram na relação financeira.", code="ineligible_rank"
            )
```

por:

```python
    def _assert_eligible(self, user: User, plan: str) -> None:
        if plan not in eligible_plans_for(user.posto_graduacao):
            raise BusinessRuleError(
                f"Posto {user.posto_graduacao or '(não informado)'} não é elegível "
                "para este plano.",
                code="ineligible_rank",
            )
```

E troque o import no topo do arquivo — remova
`from apps.accounts.models import BARBERSHOP_ONLY_RANKS, User` e use
`from apps.accounts.models import User`. Adicione `PlanCode`,
`eligible_plans_for`, `plan_price` ao import existente de `.models` (troque
a linha de import de `.models` pra incluir esses três nomes, e **remova**
`membership_fee` desse import).

- [ ] **Step 2: `activate_billing` ganha `plan`**

Substitua o método inteiro (ele já foi mexido na Fase 1 pra suportar
reativação — mantenha essa lógica, só adicionando `plan`):

```python
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
```

- [ ] **Step 3: `_create_due` usa `plan_price(profile.plan)` em vez de `membership_fee()`**

Troque:

```python
    def _create_due(self, profile: BillingProfile, period: date, today: date) -> Due:
        due_date = _due_date_for(period, profile.due_day)
        return self.dues.create(
            billing_profile=profile,
            period=period,
            due_date=due_date,
            amount=membership_fee(),
            status=self._status_for(due_date, today),
        )
```

por (só a linha `amount=` muda):

```python
    def _create_due(self, profile: BillingProfile, period: date, today: date) -> Due:
        due_date = _due_date_for(period, profile.due_day)
        return self.dues.create(
            billing_profile=profile,
            period=period,
            due_date=due_date,
            amount=plan_price(profile.plan),
            status=self._status_for(due_date, today),
        )
```

- [ ] **Step 4: `roll_all` deixa de desativar Sd/Cb**

Troque:

```python
    def roll_all(self) -> int:
        """Reconciliação diária: janela, status por data, Sd/Cb, crédito acumulado."""
        today = timezone.localdate()
        processed = 0
        for profile in self.profiles.active_profiles():
            if profile.user.posto_graduacao in BARBERSHOP_ONLY_RANKS:
                self.deactivate_billing(profile=profile)
                continue
            self._ensure_window(profile, today=today)
```

por:

```python
    def roll_all(self) -> int:
        """Reconciliação diária: janela, status por data, crédito acumulado."""
        today = timezone.localdate()
        processed = 0
        for profile in self.profiles.active_profiles():
            self._ensure_window(profile, today=today)
```

(o resto do método continua igual).

- [ ] **Step 5: Remover `membership_fee()` e `MEMBERSHIP_FEE`**

Em `backend/apps/finance/models.py`, remova a função `membership_fee()`
inteira (linhas 20-26). Em `backend/config/settings/base.py`, remova a
linha `MEMBERSHIP_FEE = env("MEMBERSHIP_FEE", default="100.00")`. Em
`backend/.env.example`, remova a linha `MEMBERSHIP_FEE=100.00`.

- [ ] **Step 6: Atualizar TODAS as chamadas de `activate_billing(` nos testes**

Em `backend/apps/finance/tests/test_finance.py`, toda chamada a
`FinanceService().activate_billing(user=..., due_day=..., started_period=...)`
precisa ganhar `plan=PlanCode.ASSOCIADO` (importe `PlanCode` de
`apps.finance.models` no topo do arquivo). Rode
`grep -n 'activate_billing(' backend/apps/finance/tests/test_finance.py`
pra listar todos os pontos (são ~24) e adicione o argumento em cada um —
exceto:

- `test_activate_billing_refuses_soldado_or_cabo` (linha ~116): **substitua
  o teste inteiro** — a premissa (Sd/Cb são recusados) não existe mais.
  Troque por:

  ```python
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
  ```

- `test_roll_all_deactivates_billing_for_soldado_or_cabo` (linha ~276):
  **remova este teste inteiro** — a premissa não existe mais (Sd/Cb agora
  ficam ativos, com o plano Mensalista Barbearia). Substitua por:

  ```python
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
  ```

- Todas as outras ~21 chamadas (as que usam usuário sem posto de praça,
  criado via `role_codes=[RoleCode.USER]` sem `posto_graduacao` — **espera,
  atenção**: `UserService().create_user(..., role_codes=[RoleCode.USER],
  ...)` sem passar `posto_graduacao` deixa o campo em branco (`""`), e pela
  matriz de elegibilidade da Task 2 um posto vazio **não é elegível pra
  nada**. Toda essa massa de testes vai quebrar com `ineligible_rank`, não
  só com `TypeError` de argumento faltando. Resolva isso passando também
  `posto_graduacao="Cel"` (ou qualquer posto fora da lista de praças) nas
  chamadas de `UserService().create_user(...)` que alimentam essas
  ativações, além de `plan=PlanCode.ASSOCIADO` na chamada de
  `activate_billing`. Confira cada `use_tenant` que cria usuário e ativa
  cobrança — se o `create_user` não tiver `posto_graduacao`, adicione
  `posto_graduacao="Cel"`.

- [ ] **Step 7: Rodar a suíte de finance até passar 100%**

```bash
docker compose exec backend pytest apps/finance -q
```

Itere nos testes até não sobrar nenhuma falha. Não pule nenhuma.

- [ ] **Step 8: Rodar a suíte inteira do backend**

```bash
docker compose exec backend pytest -q
```

`membership_fee`/`MEMBERSHIP_FEE` não são usados fora de `apps.finance` —
confirme com `grep -rn "membership_fee\|MEMBERSHIP_FEE" backend/` que não
sobrou nenhuma referência antes de rodar.

- [ ] **Step 9: Commit**

```bash
git add backend/apps/finance/services.py backend/apps/finance/models.py backend/config/settings/base.py backend/.env.example backend/apps/finance/tests/test_finance.py
git commit -m "feat(finance): elegibilidade por plano substitui a exclusão de Sd/Cb"
```

---

### Task 4: API de ativação com plano

**Files:**
- Modify: `backend/apps/finance/api/serializers.py`
- Modify: `backend/apps/finance/api/views.py`
- Modify: `backend/apps/finance/services.py` (`summary_for` ganha
  `plan`/`plan_label`)
- Modify: `backend/apps/finance/tests/test_finance.py` (todos os POSTs pra
  `/api/billing-profiles` ganham `"plan"` no corpo)

**Interfaces:**
- Consome: `PlanCode` (Task 2), `FinanceService.activate_billing(...,
  plan=...)` (Task 3).
- Produz: `BillingProfileSerializer` com `plan`/`plan_label`;
  `ActivateBillingSerializer` com `plan` obrigatório;
  `summary_for()["plan"]`/`["plan_label"]`.

- [ ] **Step 1: `plan` no `ActivateBillingSerializer` e no `BillingProfileSerializer`**

Em `backend/apps/finance/api/serializers.py`, importe `PlanCode` de
`..models` (adicione ao import existente `from ..models import
BillingProfile, Due` → `from ..models import BillingProfile, Due,
PlanCode`).

Em `ActivateBillingSerializer`, adicione o campo:

```python
    plan = serializers.ChoiceField(choices=PlanCode.choices)
```

Em `BillingProfileSerializer`, adicione `plan_label` como
`SerializerMethodField` e inclua `plan`/`plan_label` em `fields`:

```python
class BillingProfileSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.display_name", read_only=True)
    user_posto = serializers.CharField(source="user.posto_graduacao", read_only=True)
    plan_label = serializers.CharField(source="get_plan_display", read_only=True)
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
            "plan",
            "plan_label",
            "due_day",
            "started_period",
            "is_active",
            "financial_status",
            "financial_status_label",
            "last_payment_at",
        ]
        read_only_fields = ["id", "plan_label", "financial_status", "last_payment_at"]
```

(`plan` fica gravável — a criação/reativação passa por
`ActivateBillingSerializer`, não por este, então isso só afeta leitura por
enquanto; deixá-lo fora de `read_only_fields` não abre brecha nova porque
`BillingProfileViewSet.partial_update` só usa `UpdateDueDaySerializer`, que
nem toca em `plan`.)

- [ ] **Step 2: A view passa `plan` pro service**

Em `backend/apps/finance/api/views.py`, no método `create` de
`BillingProfileViewSet`, troque:

```python
        profile = self.service.activate_billing(
            user=payload.validated_data["user"],
            due_day=payload.validated_data["due_day"],
            started_period=payload.validated_data["started_period"],
            actor_id=str(request.user.pk),
        )
```

por:

```python
        profile = self.service.activate_billing(
            user=payload.validated_data["user"],
            plan=payload.validated_data["plan"],
            due_day=payload.validated_data["due_day"],
            started_period=payload.validated_data["started_period"],
            actor_id=str(request.user.pk),
        )
```

- [ ] **Step 3: `summary_for` devolve o plano**

Em `backend/apps/finance/services.py`, no método `summary_for`, adicione ao
dicionário de retorno (logo depois de `"financial_status":
profile.financial_status,`):

```python
            "plan": profile.plan,
            "plan_label": profile.get_plan_display(),
```

- [ ] **Step 4: Atualizar todo POST de teste pra `/api/billing-profiles`**

Rode `grep -n '"/api/billing-profiles"' backend/apps/finance/tests/test_finance.py`
— cada corpo de requisição (o dict logo abaixo da URL, com `"user":
str(member.id), "due_day": 10, "started_period": _period_str(0)`) ganha
`"plan": "associado"`. São ~10 ocorrências (as duas em
`test_list_billing_profiles_requires_staff_read` são GET, sem corpo — não
mexe nelas). Depois de editar, rode a suíte pra confirmar que não sobrou
nenhuma sem o campo (erro 400 de serializer indica qual).

- [ ] **Step 5: Novo teste — API recusa plano fora da elegibilidade**

Adicione:

```python
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
```

- [ ] **Step 6: Rodar a suíte de finance e a suíte inteira**

```bash
docker compose exec backend pytest apps/finance -q
docker compose exec backend pytest -q
```

- [ ] **Step 7: Commit**

```bash
git add backend/apps/finance/api/serializers.py backend/apps/finance/api/views.py backend/apps/finance/services.py backend/apps/finance/tests/test_finance.py
git commit -m "feat(finance): API de ativação exige e devolve o plano"
```

---

### Task 5: Convite do Associado — modelo, repositório, serviço, API

**Files:**
- Modify: `backend/apps/finance/models.py`
- Modify: `backend/apps/finance/repositories.py`
- Modify: `backend/apps/finance/services.py`
- Modify: `backend/apps/finance/api/serializers.py`
- Modify: `backend/apps/finance/api/views.py`
- Modify: `backend/config/api_urls.py`
- Modify: `backend/apps/finance/tests/test_finance.py`

**Interfaces:**
- Consome: `FinanceService.activate_billing(..., plan=PlanCode.ASSOCIADO,
  ...)` (Task 3).
- Produz: `AssociadoInvite` model; `FinanceService.generate_associado_invite(user,
  actor_id) -> AssociadoInvite`; `FinanceService.accept_associado_invite(token,
  actor) -> BillingProfile`; `FinanceService.list_pending_associado_invites()
  -> QuerySet[AssociadoInvite]`; endpoints `POST /finance/convites-associado`,
  `GET /finance/convites-associado`, `POST
  /finance/convites-associado/<token>/aceitar`.

- [ ] **Step 1: Model `AssociadoInvite`**

Em `backend/apps/finance/models.py`, adicione (no topo do arquivo, junto
dos outros imports, adicione `import secrets` e `from datetime import
timedelta`; `from django.utils import timezone` também precisa entrar se
ainda não estiver):

```python
def _gen_invite_token() -> str:
    return secrets.token_urlsafe(24)


def _default_invite_expiry():
    return timezone.now() + timedelta(days=settings.ASSOCIADO_INVITE_DAYS)


class AssociadoInvite(TenantScopedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="associado_invites"
    )
    token = models.CharField(max_length=64, unique=True, default=_gen_invite_token)
    expires_at = models.DateTimeField(default=_default_invite_expiry)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "associado_invite"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Convite Associado — {self.user}"

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and timezone.now() <= self.expires_at
```

- [ ] **Step 2: Migração**

```bash
docker compose exec backend python manage.py makemigrations finance
docker compose exec backend python manage.py migrate finance
```

- [ ] **Step 3: `AssociadoInviteRepository`**

Em `backend/apps/finance/repositories.py`, adicione o import de
`AssociadoInvite` (troque `from .models import OPEN_DUE_STATUSES,
BillingProfile, Due, FinanceCredit` por incluir `AssociadoInvite` também) e:

```python
class AssociadoInviteRepository(BaseRepository[AssociadoInvite]):
    model = AssociadoInvite

    def get_by_token(self, token: str) -> AssociadoInvite | None:
        return self.query().filter(token=token).first()

    def pending(self) -> models.QuerySet[AssociadoInvite]:
        return self.query().filter(used_at__isnull=True).select_related("user")
```

- [ ] **Step 4: Métodos de convite no `FinanceService`**

Em `backend/apps/finance/services.py`, adicione ao `__init__` o novo
repositório (mesma forma dos outros):

```python
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
        self.credits = credits or FinanceCreditRepository()
        self.invites = invites or AssociadoInviteRepository()
```

(atualize o import de `.repositories` no topo do arquivo pra incluir
`AssociadoInviteRepository`, e o import de `.models` pra incluir
`AssociadoInvite`.)

Adicione os métodos (em qualquer lugar depois de `activate_billing`):

```python
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
```

- [ ] **Step 5: Serializers**

Em `backend/apps/finance/api/serializers.py`, adicione:

```python
class AssociadoInviteSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.display_name", read_only=True)

    class Meta:
        model = AssociadoInvite
        fields = ["id", "user", "user_name", "token", "expires_at", "used_at", "created_at"]
        read_only_fields = fields


class GenerateInviteSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.none())

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = _tenant_users_queryset()
```

(importe `AssociadoInvite` no import de `..models` já existente no topo do
arquivo.)

- [ ] **Step 6: Views**

Em `backend/apps/finance/api/views.py`, importe `AssociadoInviteSerializer`
e `GenerateInviteSerializer` do módulo de serializers (adicione aos nomes
já importados de `.serializers`). Nenhum novo import de `..models` é
necessário aqui — a view nunca referencia `AssociadoInvite` por nome, só
passa dados pelo `FinanceService` (já importado) e serializa o resultado.
Adicione:

```python
class AssociadoInviteListCreateView(TenantContextAPIView):
    permission_classes = [IsAuthenticated]
    service = FinanceService()

    def get(self, request: Request) -> Response:
        if not _can_read(request.user):
            raise BusinessRuleError("Sem permissão para ver o financeiro.", code="forbidden")
        invites = self.service.list_pending_associado_invites()
        return Response(AssociadoInviteSerializer(invites, many=True).data)

    def post(self, request: Request) -> Response:
        if not _can_manage(request.user):
            raise BusinessRuleError("Apenas Administrador gera convites.", code="forbidden")
        payload = GenerateInviteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        invite = self.service.generate_associado_invite(
            user=payload.validated_data["user"], actor_id=str(request.user.pk)
        )
        return Response(AssociadoInviteSerializer(invite).data, status=201)


class AssociadoInviteAcceptView(TenantContextAPIView):
    permission_classes = [IsAuthenticated]
    service = FinanceService()

    def post(self, request: Request, token: str = "") -> Response:
        profile = self.service.accept_associado_invite(token=token, actor=request.user)
        return Response(BillingProfileSerializer(profile).data)
```

- [ ] **Step 7: Rotas**

Em `backend/config/api_urls.py`, importe as duas views novas de
`apps.finance.api.views` (junto de `BillingProfileViewSet, DueViewSet,
FinanceDashboardView, MyFinanceView`) e adicione ao `urlpatterns` (perto de
`"finance/me"`):

```python
    path(
        "finance/convites-associado",
        AssociadoInviteListCreateView.as_view(),
        name="associado_invites",
    ),
    path(
        "finance/convites-associado/<str:token>/aceitar",
        AssociadoInviteAcceptView.as_view(),
        name="associado_invite_accept",
    ),
```

- [ ] **Step 8: Testes**

```python
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
        invite = FinanceService().generate_associado_invite(user=cabo)
        profile = FinanceService().accept_associado_invite(token=invite.token, actor=cabo)
        invite.refresh_from_db()
    assert profile.plan == PlanCode.ASSOCIADO
    assert profile.is_active is True
    assert invite.used_at is not None


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
```

(`timedelta` já vem de `from datetime import date, datetime, timedelta` no
topo do arquivo de teste — confirme que está importado. Importe também
`PlanCode` de `apps.finance.models` se ainda não estiver, do Step 6 da
Task 3.)

- [ ] **Step 9: Rodar a suíte de finance e a suíte inteira**

```bash
docker compose exec backend pytest apps/finance -q
docker compose exec backend pytest -q
```

- [ ] **Step 10: Commit**

```bash
git add backend/apps/finance/models.py backend/apps/finance/migrations/ backend/apps/finance/repositories.py backend/apps/finance/services.py backend/apps/finance/api/serializers.py backend/apps/finance/api/views.py backend/config/api_urls.py backend/apps/finance/tests/test_finance.py
git commit -m "feat(finance): convite do Associado (gerar, listar, aceitar)"
```

---

### Task 6: Autoatendimento — assinatura própria de Mensalista Barbearia

**Files:**
- Modify: `backend/apps/finance/api/views.py`
- Modify: `backend/config/api_urls.py`
- Modify: `backend/apps/finance/tests/test_finance.py`

**Interfaces:**
- Consome: `FinanceService.activate_billing(..., plan=PlanCode.BARBEARIA,
  ...)` (Task 3) — a elegibilidade já rejeita sozinha quem não pode assinar
  Mensalista Barbearia (não-praça), sem checagem extra aqui.
- Produz: `POST /finance/me/assinar`.

- [ ] **Step 1: View de autoatendimento**

Em `backend/apps/finance/api/views.py`, adicione dois imports que ainda não
existem no arquivo: `from django.utils import timezone` (topo do arquivo,
junto dos outros imports de terceiros) e `PlanCode` junto do import
existente de `..models` (`from ..models import BillingProfile, Due` →
inclua `PlanCode`). Não importe `_first_of_month` de `..services` — é uma
função privada do módulo, não exportada; o cálculo do mês corrente é feito
direto aqui com `today.replace(day=1)`. Adicione (perto de `MyFinanceView`):

```python
class SelfSubscribeView(TenantContextAPIView):
    """Autoatendimento: o próprio usuário assina Mensalista Barbearia.

    A elegibilidade (`_assert_eligible` dentro de `activate_billing`) já
    recusa sozinha quem não é Cb/Sd EP/Sd EV — não precisa duplicar a
    checagem aqui.
    """

    permission_classes = [IsAuthenticated]
    service = FinanceService()

    def post(self, request: Request) -> Response:
        today = timezone.localdate()
        profile = self.service.activate_billing(
            user=request.user,
            plan=PlanCode.BARBEARIA,
            due_day=today.day,
            started_period=today.replace(day=1),
            actor_id=str(request.user.pk),
        )
        return Response(BillingProfileSerializer(profile).data, status=201)
```

- [ ] **Step 2: Rota**

Em `backend/config/api_urls.py`, adicione (perto de `"finance/me"`):

```python
    path("finance/me/assinar", SelfSubscribeView.as_view(), name="finance_self_subscribe"),
```

(importe `SelfSubscribeView` junto das outras views de finance.)

- [ ] **Step 3: Testes**

```python
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
```

- [ ] **Step 4: Rodar a suíte de finance**

```bash
docker compose exec backend pytest apps/finance -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/apps/finance/api/views.py backend/config/api_urls.py backend/apps/finance/tests/test_finance.py
git commit -m "feat(finance): autoatendimento de assinatura da Mensalista Barbearia"
```

---

### Task 7: Frontend — FinancePage com plano e convite

**Files:**
- Modify: `frontend/src/features/finance/api.ts`
- Modify: `frontend/src/pages/FinancePage.tsx`

**Interfaces:**
- Consome: `POST /billing-profiles` (com `plan`), `GET/POST
  /finance/convites-associado` (Task 4, Task 5).
- Produz: `eligiblePlansFor(posto: string): PlanCode[]` (helper de UI, só
  filtra o seletor — a validação de verdade é sempre no backend).

- [ ] **Step 1: Tipos e hooks novos em `features/finance/api.ts`**

Adicione ao arquivo:

```typescript
export type PlanCode = "associado" | "barbearia";

export const PLAN_LABEL: Record<PlanCode, string> = {
  associado: "Associado",
  barbearia: "Mensalista Barbearia",
};

const _BARBEARIA_ONLY: readonly string[] = ["Sd EV"];
const _BOTH_PLANS: readonly string[] = ["Sd EP", "Cb"];
const _UNCLASSIFIED: readonly string[] = ["Sd", ""];

/** Espelha `eligible_plans_for` do backend — só pra filtrar a UI; a regra
 * de verdade é sempre validada no servidor. */
export function eligiblePlansFor(posto: string): PlanCode[] {
  if (_UNCLASSIFIED.includes(posto)) return [];
  if (_BARBEARIA_ONLY.includes(posto)) return ["barbearia"];
  if (_BOTH_PLANS.includes(posto)) return ["associado", "barbearia"];
  return ["associado"];
}

export interface AssociadoInvite {
  id: string;
  user: string;
  user_name: string;
  token: string;
  expires_at: string;
  used_at: string | null;
  created_at: string;
}

export function usePendingInvites() {
  return useQuery({
    queryKey: ["finance", "invites"],
    queryFn: async () =>
      (await api.get<AssociadoInvite[]>("/finance/convites-associado")).data,
  });
}

export function useGenerateInvite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (userId: string) =>
      (await api.post<AssociadoInvite>("/finance/convites-associado", { user: userId })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "invites"] }),
  });
}
```

Atualize `BillingProfile` (adicione `plan: PlanCode;` e `plan_label:
string;` aos campos existentes) e `ActivateBillingPayload` (adicione `plan:
PlanCode;`).

- [ ] **Step 2: Seletor de plano no `ActivateBillingModal`**

Em `frontend/src/pages/FinancePage.tsx`, importe `eligiblePlansFor,
PLAN_LABEL, type PlanCode` do módulo de finance API. No estado do form
(`useState({ user: "", due_day: 10, started_period: ... })`), adicione
`plan: "" as PlanCode | ""`.

Depois do campo "Usuário" (que já filtra `candidatos` por
`posto_graduacao !== "Sd" && !== "Cb"` — **essa linha também precisa
mudar**, veja abaixo), adicione um campo de plano que só aparece depois de
escolher o usuário, filtrado pela elegibilidade dele:

```tsx
                {form.user && (
                  <div className="mb-3">
                    <label className="form-label required">Plano</label>
                    <select
                      className="form-select"
                      value={form.plan}
                      onChange={(e) => setForm((f) => ({ ...f, plan: e.target.value as PlanCode }))}
                      required
                    >
                      <option value="">Selecione…</option>
                      {eligiblePlansFor(
                        candidatos.find((u) => u.id === form.user)?.posto_graduacao ?? ""
                      ).map((code) => (
                        <option key={code} value={code}>
                          {PLAN_LABEL[code]}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
```

Troque o filtro de `candidatos` (linha 40-42):

```typescript
  const candidatos = (users ?? []).filter(
    (u) => u.posto_graduacao !== "Sd" && u.posto_graduacao !== "Cb" && !billedIds.has(u.id),
  );
```

por (agora entram todos os elegíveis pra pelo menos um plano — o filtro
antigo existia porque Sd/Cb eram excluídos por completo; isso não vale
mais):

```typescript
  const candidatos = (users ?? []).filter(
    (u) => eligiblePlansFor(u.posto_graduacao).length > 0 && !billedIds.has(u.id),
  );
```

E troque a dica de texto logo abaixo do `<select>` de usuário (linha 84,
`"Praças (Sd/Cb) não aparecem — não entram na relação."`) por
`"Só aparecem usuários com posto elegível a algum plano."`.

Certifique que `UserRef`/o tipo de `users` (de `useUsers()`, em
`features/accounts/api.ts`) expõe `posto_graduacao` — se não expuser,
adicione ao tipo e ao serializer de usuários do backend (`UserSerializer`
em `apps/accounts/api/serializers.py`) o campo `posto_graduacao` (é
provável que já esteja lá, já que `UsersPage.tsx` e o próprio
`ActivateBillingModal` atual já mostram o posto — confirme antes de mexer).

- [ ] **Step 3: `plan` no payload de ativação**

No `submit` do `ActivateBillingModal`, o `form` já vai incluir `plan`
porque está no estado — nenhuma mudança extra, só garanta que o `<button
type="submit">` fica desabilitado se `!form.plan` (adicione `|| !form.plan`
à condição `disabled={activate.isPending}` → `disabled={activate.isPending
|| !form.plan}`).

- [ ] **Step 4: Coluna "Plano" na tabela + convite pra Cb/Sd EP sem cobrança**

Adicione uma coluna `<th>Plano</th>` na tabela (depois de "Posto/Grad.") e
a célula correspondente `<td>{p.plan_label}</td>`.

Abaixo da tabela de perfis, adicione uma seção pra convites pendentes e
geração de novo convite — busque `usePendingInvites()` e `useUsers()`,
filtre usuários com `eligiblePlansFor(u.posto_graduacao).includes("associado")
&& eligiblePlansFor(u.posto_graduacao).includes("barbearia")` (ou seja,
exatamente os que têm escolha — Cb/Sd EP) e que ainda não têm
`BillingProfile` ativo nem convite pendente:

```tsx
function AssociadoInvites() {
  const { data: invites } = usePendingInvites();
  const { data: users } = useUsers();
  const { data: profiles } = useBillingProfiles();
  const generate = useGenerateInvite();
  const [link, setLink] = useState<string | null>(null);

  const billedIds = new Set((profiles ?? []).map((p) => p.user));
  const invitedIds = new Set((invites ?? []).filter((i) => !i.used_at).map((i) => i.user));
  const candidatos = (users ?? []).filter(
    (u) =>
      eligiblePlansFor(u.posto_graduacao).length === 2 &&
      !billedIds.has(u.id) &&
      !invitedIds.has(u.id),
  );

  return (
    <div className="card mt-3">
      <div className="card-header">
        <h3 className="card-title">Convite para o Associado</h3>
      </div>
      <div className="card-body">
        {link && (
          <div className="alert alert-success">
            Link gerado: <code>{link}</code>
          </div>
        )}
        <p className="text-secondary">
          Cabos e Soldados EP podem escolher entre Associado e Mensalista
          Barbearia. Gere um convite pra deixar a pessoa escolher ela mesma.
        </p>
        <select
          className="form-select mb-2"
          defaultValue=""
          onChange={async (e) => {
            if (!e.target.value) return;
            const invite = await generate.mutateAsync(e.target.value);
            setLink(`${window.location.origin}/convite/associado/${invite.token}`);
            e.target.value = "";
          }}
        >
          <option value="">Gerar convite para…</option>
          {candidatos.map((u) => (
            <option key={u.id} value={u.id}>
              {u.display_name || u.username}
            </option>
          ))}
        </select>
        {(invites ?? []).filter((i) => !i.used_at).length > 0 && (
          <table className="table table-sm mt-2">
            <tbody>
              {(invites ?? [])
                .filter((i) => !i.used_at)
                .map((i) => (
                  <tr key={i.id}>
                    <td>{i.user_name}</td>
                    <td className="text-secondary small">
                      expira {new Date(i.expires_at).toLocaleDateString("pt-BR")}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
```

Renderize `{canManage && <AssociadoInvites />}` logo depois da tabela
principal, dentro de `FinancePage`.

- [ ] **Step 5: `npm run lint`**

```bash
cd frontend && npm run lint
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/finance/api.ts frontend/src/pages/FinancePage.tsx
git commit -m "feat(financeiro): seletor de plano e convite do Associado no painel admin"
```

---

### Task 8: Frontend — tela de aceite do convite

**Files:**
- Create: `frontend/src/pages/AssociadoInvitePage.tsx`
- Modify: `frontend/src/features/finance/api.ts`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consome: `POST /finance/convites-associado/<token>/aceitar` (Task 5).

- [ ] **Step 1: Hook de aceite**

Em `frontend/src/features/finance/api.ts`, adicione:

```typescript
export function useAcceptAssociadoInvite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (token: string) =>
      (await api.post<BillingProfile>(`/finance/convites-associado/${token}/aceitar`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}
```

- [ ] **Step 2: Página de aceite**

Crie `frontend/src/pages/AssociadoInvitePage.tsx`:

```tsx
import { IconUsers } from "@tabler/icons-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useAcceptAssociadoInvite } from "../features/finance/api";

export default function AssociadoInvitePage() {
  const { token = "" } = useParams();
  const accept = useAcceptAssociadoInvite();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  async function confirmar() {
    setError(null);
    try {
      await accept.mutateAsync(token);
      navigate("/perfil", { replace: true });
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response
        ?.data?.error?.message;
      setError(msg ?? "Não foi possível aceitar o convite.");
    }
  }

  return (
    <div className="page page-center">
      <div className="container container-tight py-4">
        <div className="card card-md">
          <div className="card-body text-center py-5">
            <IconUsers size={40} className="mb-3 text-primary" />
            <h2 className="mb-2">Convite para o Associado</h2>
            <p className="text-secondary mb-4">
              R$ 30,00 por mês, com direito a 4 cortes na barbearia. Confirmar
              ativa a cobrança a partir de hoje.
            </p>
            {error && <div className="alert alert-danger">{error}</div>}
            <button className="btn btn-primary w-100" onClick={confirmar} disabled={accept.isPending}>
              {accept.isPending ? "Confirmando…" : "Aceitar e virar Associado"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Rota**

Em `frontend/src/App.tsx`, importe `AssociadoInvitePage` (junto dos outros
imports de página) e adicione a rota dentro de `<Route element={<RequireAuth
/>}>`, antes do `<Route element={<Layout />}>` (mesmo nível de `/modulos` —
tela cheia, sem o layout com menu):

```tsx
        <Route path="/convite/associado/:token" element={<AssociadoInvitePage />} />
```

- [ ] **Step 4: `npm run lint`**

```bash
cd frontend && npm run lint
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/AssociadoInvitePage.tsx frontend/src/features/finance/api.ts frontend/src/App.tsx
git commit -m "feat(financeiro): tela de aceite do convite do Associado"
```

---

### Task 9: Frontend — card "Meu plano" com autoatendimento no Perfil

**Files:**
- Modify: `frontend/src/features/finance/api.ts` (`MyFinanceSummary` ganha
  `plan`/`plan_label`)
- Modify: `frontend/src/pages/ProfilePage.tsx`

**Interfaces:**
- Consome: `GET /finance/me` (agora com `plan`/`plan_label`, Task 4),
  `POST /finance/me/assinar` (Task 6).

- [ ] **Step 1: Tipo `MyFinanceSummary`**

Em `frontend/src/features/finance/api.ts`, adicione `plan: string;` e
`plan_label: string;` à interface `MyFinanceSummary`. Adicione também:

```typescript
export function useSelfSubscribe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => (await api.post<BillingProfile>("/finance/me/assinar")).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}
```

- [ ] **Step 2: `FinanceCard` mostra o plano; card de "sem plano" pra quem é elegível**

Em `frontend/src/pages/ProfilePage.tsx`, importe `eligiblePlansFor,
PLAN_LABEL, useSelfSubscribe` de `../features/finance/api`.

No `FinanceCard` existente, adicione o plano ao lado da situação (no
`card-header`, depois do `<h3 className="card-title m-0">Minha
mensalidade</h3>`):

```tsx
        <span className="text-secondary small">{data.plan_label}</span>
```

Adicione um novo componente, renderizado só quando `useMyFinance()` não
tem perfil ativo (`data` é `null`):

```tsx
function NoPlanCard() {
  const { user } = useAuth();
  const { data, isLoading } = useMyFinance();
  const subscribe = useSelfSubscribe();
  const [error, setError] = useState<string | null>(null);

  if (isLoading || data) return null;
  const posto = user?.posto_graduacao ?? "";

  if (posto === "Sd") {
    return (
      <div className="card mt-3">
        <div className="card-body">
          <div className="alert alert-warning mb-0">
            Seu posto está desatualizado (Soldado, sem EP/EV). Peça pro
            administrador corrigir seu cadastro antes de assinar um plano.
          </div>
        </div>
      </div>
    );
  }

  const podeBarbearia = eligiblePlansFor(posto).includes("barbearia");

  async function assinar() {
    setError(null);
    try {
      await subscribe.mutateAsync();
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } }).response
        ?.data?.error?.message;
      setError(msg ?? "Não foi possível ativar a assinatura.");
    }
  }

  return (
    <div className="card mt-3">
      <div className="card-header">
        <h3 className="card-title m-0">Meu plano</h3>
      </div>
      <div className="card-body">
        {error && <div className="alert alert-danger">{error}</div>}
        <p className="text-secondary">Sem plano ativo.</p>
        {podeBarbearia ? (
          <button className="btn btn-primary" onClick={assinar} disabled={subscribe.isPending}>
            {subscribe.isPending ? "Ativando…" : `Assinar ${PLAN_LABEL.barbearia}`}
          </button>
        ) : (
          <a href="/barbearia" className="btn btn-outline-primary">
            Marcar corte avulso
          </a>
        )}
      </div>
    </div>
  );
}
```

Renderize `<NoPlanCard />` logo depois de `<FinanceCard />` em
`ProfilePage`.

- [ ] **Step 3: `npm run lint`**

```bash
cd frontend && npm run lint
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/finance/api.ts frontend/src/pages/ProfilePage.tsx
git commit -m "feat(financeiro): card de plano no perfil, com autoatendimento"
```

---

### Task 10: Frontend — postos pendentes de reclassificação em Usuários

**Files:**
- Modify: `frontend/src/pages/UsersPage.tsx`

**Interfaces:**
- Nenhuma nova — só leitura do campo `posto_graduacao` já exposto.

- [ ] **Step 1: Badge de posto pendente na tabela**

Em `frontend/src/pages/UsersPage.tsx`, na célula que mostra o posto de cada
usuário na tabela principal, adicione um badge de aviso quando
`posto_graduacao === "Sd"` (valor legado, exato, sem "EP"/"EV"):

```tsx
{u.posto_graduacao === "Sd" && (
  <span className="badge bg-yellow-lt ms-1" title="Posto desatualizado — precisa virar Sd EP ou Sd EV">
    pendente
  </span>
)}
```

Ajuste o JSX de acordo com a estrutura real da célula de posto (leia o
arquivo antes de editar — a tabela já existe, essa é uma adição pontual).

- [ ] **Step 2: Filtro rápido**

Adicione um toggle/checkbox "Só pendentes de reclassificação" perto dos
filtros já existentes da tabela, que quando ativo filtra a lista pra só
`posto_graduacao === "Sd"`.

- [ ] **Step 3: `npm run lint`**

```bash
cd frontend && npm run lint
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/UsersPage.tsx
git commit -m "feat(usuarios): sinaliza postos pendentes de reclassificação (Sd legado)"
```

---

### Task 11: Verificação manual end-to-end

**Files:** nenhum — só verificação. A stack já está rodando via `docker
compose up`.

- [ ] **Step 1: Criar usuários de teste descartáveis**

```bash
docker compose exec backend python manage.py shell -c "
from apps.accounts.models import RoleCode, User
from apps.accounts.services import UserService
from core.context import use_tenant
tenant_id = User.objects.filter(roles__code=RoleCode.ADMIN).first().tenant_id
with use_tenant(tenant_id):
    UserService().create_user(
        username='qa.cabo@example.com', password='supersecret123',
        email='qa.cabo@example.com', full_name='QA Cabo', posto_graduacao='Cb',
        role_codes=[RoleCode.USER], tenant_id=tenant_id,
    )
    UserService().create_user(
        username='qa.coronel@example.com', password='supersecret123',
        email='qa.coronel@example.com', full_name='QA Coronel', posto_graduacao='Cel',
        role_codes=[RoleCode.USER], tenant_id=tenant_id,
    )
print('created')
"
```

- [ ] **Step 2: Admin ativa Associado direto pro Coronel**

Login como admin, `/financeiro` → "Ativar cobrança" → QA Coronel → só
"Associado" aparece no seletor de plano → ativa. Confirma que aparece na
tabela com "Associado" na coluna Plano.

- [ ] **Step 3: Admin gera convite Associado pro Cabo**

Na seção "Convite para o Associado", gera convite pro QA Cabo. Confirma que
o link aparece e que o cabo some da lista de candidatos a novo convite.

- [ ] **Step 4: Cabo aceita o convite**

Logout, login como `qa.cabo@example.com`. Abre o link `/convite/associado/<token>`
copiado no passo anterior. Confirma → volta pro perfil → card "Minha
mensalidade" mostra "Associado".

- [ ] **Step 5: Autoatendimento de Mensalista Barbearia**

Cria mais um usuário QA com posto "Sd EV" (via shell, como no Step 1).
Login como ele, `/perfil` → card "Meu plano" mostra "Sem plano ativo" com
botão "Assinar Mensalista Barbearia" → clica → confirma que vira "Minha
mensalidade: Mensalista Barbearia".

- [ ] **Step 6: Posto legado "Sd" não assina nada**

Cria (ou edita um QA existente pra) posto "Sd" (bare, sem EP/EV) via shell
direto no banco (o dropdown do frontend não oferece mais essa opção — é só
pra simular um usuário legado):

```bash
docker compose exec backend python manage.py shell -c "
from apps.accounts.models import User
u = User.objects.get(username='qa.cabo@example.com')
u.posto_graduacao = 'Sd'
u.save(update_fields=['posto_graduacao'])
"
```

Login como esse usuário → `/perfil` → card mostra o aviso de posto
desatualizado, sem botão de assinar.

- [ ] **Step 7: Limpeza**

```bash
docker compose exec backend python manage.py shell -c "
from apps.accounts.models import User
for uname in ['qa.cabo@example.com', 'qa.coronel@example.com']:
    u = User.objects.filter(username=uname).first()
    if u:
        u.is_active = False
        u.save(update_fields=['is_active'])
print('deactivated')
"
```

Sem commit nesta task — se algum passo falhar, volte pra task
correspondente e corrija antes de considerar o plano concluído.
