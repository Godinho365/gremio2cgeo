# Módulo Financeiro — Fase 1 (Núcleo) — Design

Data: 2026-08-29
Status: aprovado

## Contexto

O sistema tem um módulo "Financeiro" reservado no menu desde a feature da
Barbearia (`MODULES` em `frontend/src/modules.ts`, `available: false`) e uma
tela stub (`FinancePage.tsx`, "Em desenvolvimento"). O pedido do usuário é o
requisito completo de controle de mensalidades do grêmio: geração automática,
pagamento (manual e Pix), antecipação, status por período e agregado por
usuário, histórico e dashboard administrativo.

**Decisão de escopo — duas fases:**
- **Fase 1 (este documento e o plano que segue):** modelo de dados, geração
  automática de mensalidade, lançamento manual de pagamento (com alocação
  automática de antecipação), status, histórico, dashboard e tela admin. Já
  100% operável pelo admin sem depender de gateway de pagamento.
- **Fase 2 (fora de escopo aqui, spec própria quando chegar a vez):**
  pagamento via Pix pelo próprio usuário, reaproveitando o
  `MercadoPagoGateway` já usado na barbearia (`apps/payments/gateways/`).

## App novo: `apps/finance`

Segue o padrão de camadas do projeto (`View/Serializer → Service →
Repository → Model`), mesmo estilo dos apps `scheduling`/`custody`.

## Modelo de dados

### `BillingProfile` (`billing_profile`)

Um por usuário — só existe para quem foi **ativado** na relação financeira
(nem todo usuário precisa estar aqui).

| Campo | Tipo | Observação |
|---|---|---|
| `user` | FK única (`User`) | |
| `due_day` | `PositiveSmallIntegerField` (1–31) | dia fixo de vencimento |
| `started_period` | `DateField` | 1º dia do mês/ano em que a cobrança começa (definido pelo admin na ativação) |
| `is_active` | `bool`, default `True` | desativado = sai da relação, mas o histórico de `Due` permanece |
| `financial_status` | `CharField` (choices `FinancialStatus`) | agregado do usuário, recalculado diariamente (ver "Situação Financeira" abaixo) — denormalizado para o dashboard não precisar varrer todas as `Due` de todos os usuários a cada consulta |
| `last_payment_at` | `DateTimeField`, null | denormalizado, atualizado a cada pagamento liquidado |

`TenantScopedModel` (como todo o resto do sistema).

**Regra de ativação:** a Service recusa ativar `BillingProfile` para usuário
com `posto_graduacao` em `{"Sd", "Cb"}` — checagem direta no posto, não via
o papel `barbershop_client` da feature anterior. São regras de negócio
independentes (uma é sobre acesso a módulo, esta é sobre cobrança) que hoje
coincidem por causa da regra dura de posto já existente, mas não devem ficar
acopladas — se um dia deixarem de coincidir, cada regra continua correta por
si.

**Regra de desativação automática:** se o posto de um usuário com
`BillingProfile` ativo virar Sd/Cb depois (via qualquer um dos pontos que já
aplicam a regra de posto — `create_user`/`update_user`/`update_profile`), o
`FinanceService` desativa o perfil automaticamente. Isso é chamado a partir
de `UserService` (que já é quem detecta a mudança de posto) — um hook simples,
não um sinal Django (mantém explícito e testável).

### `Due` (`due`) — uma mensalidade de um usuário em um período

| Campo | Tipo | Observação |
|---|---|---|
| `billing_profile` | FK | |
| `period` | `DateField` | sempre dia 1 do mês (ex: `2026-08-01`) |
| `due_date` | `DateField` | `period` + `due_day`, truncado ao último dia do mês quando `due_day` não existe naquele mês (ex: dia 31 em fevereiro → 28/29) |
| `amount` | `DecimalField` | snapshot do `MEMBERSHIP_FEE` no momento da geração — mensalidades já geradas não mudam se o valor global mudar depois |
| `status` | `CharField` (choices `DueStatus`) | ver abaixo |
| `paid_in_advance` | `bool`, default `False` | `True` quando liquidada antes do próprio mês começar (ver "Alocação de pagamento") — é uma marca informativa, não um status separado |
| `settled_by` | FK `Payment`, null | quem liquidou esta mensalidade |
| `paid_at` | `DateTimeField`, null | denormalizado de `settled_by.paid_at` para consulta rápida no histórico |

Índice único `(billing_profile, period)` — nunca duas `Due` para o mesmo
usuário no mesmo mês.

`DueStatus` (6 valores, só o **não-pago** muda com o tempo):
```
PENDING     "Pendente"           — gerada, ainda longe do vencimento
DUE_SOON    "Próximo do vencimento"  — due_date a até 5 dias
DUE_TODAY   "Vencendo hoje"      — due_date é hoje
OVERDUE     "Vencido"            — até 15 dias após due_date
DELINQUENT  "Inadimplente"       — mais de 15 dias após due_date
PAID        "Pago"               — liquidada (o `paid_in_advance` acima
                                    diferencia "pago no prazo/atrasado" de
                                    "pago adiantado", sem precisar de um
                                    status próprio — bate com o exemplo do
                                    pedido, onde agosto a dezembro aparecem
                                    todos como "✅ Pago" e só a leitura
                                    agregada por usuário fala em
                                    "antecipado")
```

### `FinancialStatus` (agregado por usuário, vive em `BillingProfile.financial_status`)

```
UP_TO_DATE       "Em dia"                 🟢
PAID_IN_ADVANCE  "Pago antecipadamente"   🔵
DUE_SOON         "Próximo do vencimento"  🟡
DUE_TODAY        "Vencendo hoje"          🟠
OVERDUE          "Vencido"                🔴
DELINQUENT       "Inadimplente"           ⛔
```

Precedência (pior caso vence), calculada sobre todas as `Due` do usuário:
`DELINQUENT` > `OVERDUE` > `DUE_TODAY` > `DUE_SOON` > (nenhuma pendência e a
última `Due` paga tem `period` no futuro em relação ao mês atual →
`PAID_IN_ADVANCE`) > `UP_TO_DATE`.

### `FinanceCredit` (`finance_credit`) — extrato de crédito por resto de pagamento

Mesmo padrão do `CreditEntry` que a barbearia já usa (`apps/payments/models.py`):
saldo é sempre a soma das linhas, nunca um campo solto.

| Campo | Tipo | Observação |
|---|---|---|
| `billing_profile` | FK | |
| `amount` | `DecimalField` | positivo = crédito gerado, negativo = crédito consumido |
| `reason` | `CharField` (choices: `OVERPAYMENT` "Resto de pagamento", `CONSUMED` "Usado em mensalidade", `REVERSED` "Estornado", `MANUAL` "Ajuste da administração") | |
| `payment` | FK `Payment`, null | o pagamento que gerou o resto, quando houver |
| `due` | FK `Due`, null | a mensalidade que consumiu o crédito, quando houver |
| `note` | `CharField`, blank | |

## Reaproveitamento de `apps/payments`

`Payment` (`backend/apps/payments/models.py`) já é genérico — `payer`,
`amount`, `method`, `status`, tenant-scoped, sem nada específico de
barbearia. Reaproveitado aqui em vez de duplicar o conceito de
"cobrança/recibo":

- `PaymentMethod` ganha `DINHEIRO` e `TRANSFERENCIA` (além do `PIX`
  existente).
- Lançamento manual cria um `Payment` com `status=APPROVED`,
  `paid_at=<informado pelo admin>`, `provider=""` (só Pix tem provedor).
- `Due.settled_by` aponta pra esse `Payment`. Um `Payment` pode liquidar
  várias `Due` (a relação é `Due → Payment`, não M2M — cada mensalidade tem
  no máximo um pagamento que a liquidou; um pagamento pode aparecer em
  várias mensalidades via `related_name="dues_settled"`).

## Regras de negócio (`FinanceService`)

### Geração de mensalidade

Na ativação do `BillingProfile`: gera `period` atual + 2 meses à frente,
todas `PENDING` (ou já com o status correto se `due_date` já passou —
acontece se o admin ativar retroativo). A task diária (ver Automação) estende
a janela e recalcula status das não pagas.

### Alocação de pagamento (`register_payment`)

```
entrada: user, amount, method, paid_at, actor
1. pega as Due não pagas do usuário em ordem cronológica (period asc)
2. quantos_periodos = floor(amount / MEMBERSHIP_FEE)
3. se quantos_periodos > quantas Due não pagas já existem, gera as que
   faltarem (estendendo além da janela normal de 2 meses)
4. para cada uma das `quantos_periodos` primeiras Due (mais antigas primeiro):
   - cria (ou reaproveita, se for a mesma chamada) um Payment
   - due.status = PAID
   - due.paid_in_advance = due.period é posterior ao 1º dia do mês que
     contém paid_at (ou seja: o mês do período ainda nem tinha começado
     quando o pagamento caiu)
   - due.settled_by = payment; due.paid_at = paid_at
5. resto = amount - (quantos_periodos * MEMBERSHIP_FEE)
   se resto > 0: guarda como crédito (ver abaixo), aplicado automaticamente
   à próxima Due que for gerada ou já existir em aberto
6. recalcula billing_profile.financial_status e last_payment_at
```

**Crédito de resto:** mesmo padrão de `CreditEntry` que a barbearia já usa —
uma tabela de lançamentos (`FinanceCredit`, positivo = crédito disponível,
negativo = uso), saldo é a soma, nunca um campo solto. Ao gerar uma nova
`Due` para um usuário com saldo de crédito positivo, a Service consome o
crédito automaticamente até o limite do valor da mensalidade.

### Cancelamento de pagamento

Admin-only. Reabre todas as `Due` que aquele `Payment` liquidou (volta pra
`PENDING`/recalcula status pela data), e estorna qualquer crédito que
aquele pagamento tivesse gerado. Auditado (`AuditLog`).

## API (`config/api_urls.py`)

- `BillingProfileViewSet` (`/api/finance/profiles`) — leitura: `STAFF_ROLES`
  (mesmo grupo que já vê o item "Financeiro" hoje); escrita (ativar, editar
  due_day, desativar): `_MANAGE_ROLES = (RoleCode.ADMIN,)`.
- `DueViewSet` (`/api/finance/dues`) — leitura: `STAFF_ROLES`. Ações:
  - `POST /api/finance/dues/registrar-pagamento` — admin-only.
  - `POST /api/finance/dues/{id}/cancelar-pagamento` — admin-only.
- `GET /api/finance/dashboard` — `STAFF_ROLES`. Indicadores: total de
  usuários na relação, em dia, inadimplentes, mensalidades a vencer (30
  dias), mensalidades vencidas, pagamentos recebidos no período (parâmetros
  `from`/`to`), valores em aberto, valores recebidos antecipadamente,
  previsão de recebimento (soma de `amount` de `Due` não vencidas com
  `due_date` nos próximos 30 dias).
- `GET /api/finance/me` — usuário autenticado vê a própria situação
  (perfil ativo, próxima mensalidade, dias até o vencimento, meses pagos,
  meses pagos antecipadamente, meses em aberto, valor total pendente, último
  pagamento, período pago até). 404 se não estiver na relação.

## Frontend

- `frontend/src/modules.ts`: `financeiro.available = true`;
  `roles: STAFF_ROLES` (leitura do módulo).
- `FinancePage.tsx` deixa de ser stub: dashboard (cards dos indicadores) +
  tabela de usuários na relação (posto, situação com badge colorida —
  mapeando as 6 cores do `FinancialStatus`, próximo vencimento, valor
  pendente), com "Ativar cobrança" para quem ainda não está e "Ver extrato"
  para quem já está. Ações de escrita (ativar, registrar pagamento,
  cancelar) só aparecem pra admin.
- Tela de extrato por usuário: histórico de `Due` + modal "Registrar
  pagamento" (valor, forma, data — mostra em tempo real quantos meses
  aquele valor cobre, igual ao exemplo do pedido, antes de confirmar).
- `ProfilePage.tsx` ganha um card "Minha mensalidade" (mesmo estilo do
  `CreditCard` da barbearia), só visível se o usuário estiver na relação —
  mostra situação, próximo vencimento, meses pagos. Sem ação de pagamento
  nesta fase (isso é Fase 2).

## Automação (Celery beat)

Nova entrada em `CELERY_BEAT_SCHEDULE`:
```python
"roll-finance-dues": {
    "task": "finance.roll_dues",
    "schedule": crontab(hour=1, minute=0),  # uma vez por dia, de madrugada
},
```
A task, para cada `BillingProfile` ativo: garante a janela de mensalidades
futuras gerada (consumindo crédito pendente, se houver), recalcula o
`status` de toda `Due` em aberto conforme a data de hoje, e recalcula
`financial_status` do perfil.

Config nova em `config/settings/base.py`: `MEMBERSHIP_FEE = env("MEMBERSHIP_FEE", default="100.00")` — mesmo padrão do `WALK_IN_PRICE`.

## Testes

`backend/apps/finance/tests/`:
- Geração respeita `due_day`, inclusive mês curto (dia 31 → último dia de
  fevereiro).
- Transições de status por data (`PENDING → DUE_SOON → DUE_TODAY → OVERDUE
  → DELINQUENT`) nos limites exatos (5 dias, 0 dias, 15 dias).
- Alocação de pagamento: o exemplo do pedido (mensalidade R$100, pagamento
  de R$500 → agosto a dezembro pagos, janeiro pendente) como teste direto;
  pagamento com resto gera crédito; crédito é consumido na próxima geração.
- `FinancialStatus` agregado bate com a precedência descrita, em cada
  combinação relevante.
- Ativação recusa Sd/Cb; mudança de posto para Sd/Cb desativa o perfil
  automaticamente.
- RBAC: admin gerencia, staff lê, usuário comum não acessa endpoints de
  gestão; `GET /api/finance/me` funciona pro próprio usuário.
- Isolamento de tenant (padrão já coberto em todo app novo).

## Fora de escopo (Fase 1)

- Pagamento via Pix pelo usuário (Fase 2).
- Edição de valor de mensalidade por usuário (só valor único global, por
  enquanto).
- Notificações (e-mail/push) de vencimento próximo — o pedido não menciona,
  fica como possível Fase 3.
- Geração retroativa em massa para usuários já cadastrados — cada usuário
  entra na relação quando o admin ativa explicitamente, com o mês/ano de
  início que ele definir.
