# Planos da Barbearia e Integração com o Financeiro — Design (Fase 2 do Financeiro)

## Contexto

O Módulo Financeiro (Fase 1) cobra uma mensalidade única (`MEMBERSHIP_FEE`) de
todo mundo, **exceto** Cb e Sd — essa praças ficam de fora da relação
financeira por completo (`BARBERSHOP_ONLY_RANKS`).

O requisito original desta Fase 2:

| Plano                    |    Valor | Elegibilidade                        | Cortes mensais |
| ------------------------ | -------: | ------------------------------------ | -------------: |
| **Associado**            | R$ 30,00 | Todos os elegíveis, **exceto Sd EV** |              4 |
| **Mensalista Barbearia** | R$ 20,00 | **Cb, Sd EP e Sd EV**                |              4 |
| **Corte Avulso**         | R$ 15,00 | Qualquer usuário                     |               1 |

Mais três exigências: todo usuário do sistema aparece no financeiro (fim da
exclusão de Cb/Sd); o perfil mostra o plano ativo (Corte Avulso não é plano —
sem plano ativo, a situação é "Inativo", com opção de pagar corte avulso);
notificação in-app quando a pessoa precisa regularizar.

## Decisões já validadas

- **Sd vira dois postos**: "Sd EP" e "Sd EV" substituem o atual "Sd" genérico
  no cadastro (não fica um campo extra — o posto em si passa a ser um dos
  dois).
- **Associado exige convite**: para Cb/Sd EP (que são elegíveis pros dois
  planos pagos), o Administrador gera um link de convite por usuário; sem
  convite, esse usuário só vê Mensalista Barbearia e Corte Avulso como
  opção. Quem só é elegível pro Associado (postos não-praça) continua
  ativado direto pelo admin, sem convite — não há escolha a proteger.
- **Cota trava a agenda**: estourar os cortes do mês impede novo agendamento
  até o mês seguinte.
- **Notificação é escopo novo**: não existe nenhuma central de notificações
  hoje.

## Achado importante durante a investigação

`apps.barbershop` já resolve duas peças que eu esperava construir do zero:

- `walk_in_price()` (`settings.WALK_IN_PRICE`, padrão R$ 15,00) **já é o
  Corte Avulso** — mesmo valor do requisito. Nada novo aqui.
- `SUBSCRIBER_MONTHLY_LIMIT = 3` **já é a cota mensal do assinante** — só
  precisa virar 4.

Só que `is_subscriber` (o campo que decide se o corte é grátis + conta cota,
ou se cobra `walk_in_price()`) é hoje **um boolean que o próprio cliente
manda na requisição de agendamento** (`AppointmentCreateSerializer`), sem
nenhuma conferência no servidor contra o Financeiro — porque quando a
barbearia foi construída, o Financeiro ainda não existia. Ou seja, hoje
qualquer usuário autenticado pode marcar `is_subscriber: true` e ganhar o
corte de graça. Fechar essa lacuna é parte necessária de "a cota trava a
agenda" — do contrário a trava não vale nada.

## 1. Postos: Sd → Sd EP / Sd EV

- `frontend/src/features/accounts/api.ts` (`MILITARY_RANKS`, grupo
  "Praças"): remove a opção `{ value: "Sd", label: "Soldado" }`, adiciona
  `{ value: "Sd EP", label: "Soldado EP" }` e `{ value: "Sd EV", label:
  "Soldado EV" }`. "Cb" fica como está.
- `backend/apps/accounts/models.py`: `BARBERSHOP_ONLY_RANKS` passa de
  `frozenset({"Sd", "Cb"})` para `frozenset({"Sd EP", "Sd EV", "Cb"})` — a
  regra de acesso (força o perfil "Cliente da Barbearia", sem Patrimônio)
  continua valendo pra a mesma população, agora nomeada com os dois novos
  valores. Essa regra **não muda de comportamento**, só de rótulo.
- **Dados existentes**: usuários com `posto_graduacao = "Sd"` (valor livre,
  sem enum no banco) ficam como estão — nenhuma migração tenta adivinhar
  EP ou EV. A partir da mudança, o dropdown só oferece as duas opções novas,
  então qualquer edição futura do cadastro força a escolha. Enquanto não for
  reclassificado, esse usuário **não é elegível pra nenhum plano** (nem
  Associado, nem Mensalista Barbearia) e o Financeiro mostra um aviso
  pedindo a correção do posto. A tela de Usuários ganha um filtro/lista de
  "postos pendentes de reclassificação" pro admin acompanhar — não é um
  modal bloqueante, só visibilidade.

## 2. Planos financeiros (`apps.finance`)

Troca o valor único (`membership_fee()`) por dois planos:

```python
class PlanCode(models.TextChoices):
    ASSOCIADO = "associado", "Associado"
    BARBEARIA = "barbearia", "Mensalista Barbearia"

def plan_price(code: str) -> Decimal:
    # settings.ASSOCIADO_FEE (padrão 30.00) / settings.BARBEARIA_FEE (padrão 20.00)
    # mesmo padrão de leitura tardia do membership_fee() atual.
```

`BillingProfile` ganha `plan = CharField(choices=PlanCode.choices)`
(obrigatório). Geração de `Due` passa a gravar `plan_price(profile.plan)` em
vez de `membership_fee()` — a mecânica de `Due`/`Payment`/`FinanceCredit`
(ledger, alocação, cancelamento, crédito) não muda nada, só a origem do
valor.

### Matriz de elegibilidade

| Posto                              | Associado | Mensalista Barbearia |
| ----------------------------------- | :-------: | :-------------------: |
| Sd EV                               |     —     |           ✅           |
| Sd EP, Cb                           |     ✅ *   |           ✅           |
| Qualquer outro (graduado/oficial)   |     ✅     |           —            |

\* só com convite válido (ver seção 3).

`_refuse_if_ineligible` (hoje: recusa Sd/Cb inteiramente) vira uma checagem
de plano-por-posto: recusa se o plano pedido não está na lista de elegíveis
daquele posto. `roll_all` deixa de desativar cobrança de Sd/Cb — essa
população agora tem cobrança de verdade.

`activate_billing` ganha o parâmetro `plan`; a reativação (da Fase 1) também
passa a aceitar trocar o plano, do mesmo jeito que já aceita trocar
`due_day`.

## 3. Convite do Associado

Novo model pequeno, tenant-scoped: `AssociadoInvite` (token único, `user`,
`created_by`, `expires_at`, `used_at` nulo até ser consumido).

Fluxo: no cadastro do usuário elegível a escolha (Cb/Sd EP), o Administrador
clica "Gerar convite Associado" → sistema cria o token e mostra um link
(`/convite/associado/<token>`) pra ele copiar e mandar por fora (WhatsApp,
e-mail). A pessoa convidada, autenticada no sistema, abre o link → tela
simples confirmando "R$ 30,00/mês, 4 cortes" → confirma → ativa a cobrança
no plano Associado (`activate_billing(plan=ASSOCIADO, via_invite=True)`,
marcando o convite como usado). Sem visitar o link, o autoatendimento desse
usuário só oferece Mensalista Barbearia e Corte Avulso.

Quem só é elegível pro Associado (não-praça) não precisa de convite: o admin
ativa direto pela tela já existente de "Ativar cobrança", como hoje —
simplesmente sem opção de escolher outro plano.

**Duas suposições minhas que preciso que você confirme:**

1. O formato do convite (link individual por usuário, gerado pelo admin,
   consumido pela própria pessoa) — se for outra coisa (ex.: link genérico,
   não por usuário), me avisa.
2. **Isto introduz autoatendimento pela primeira vez** — a Fase 1 do
   Financeiro foi desenhada com gestão 100% restrita ao Administrador ("só
   pelo admin" foi a escolha explícita na época). Este spec assume que
   Mensalista Barbearia (e o Associado via convite) passam a ter uma tela de
   autoatendimento onde o próprio usuário ativa a cobrança dele. Se você
   preferir manter tudo admin-driven — ou seja, o convite vira só uma
   permissão que o admin confere antes de ativar o Associado ele mesmo pela
   tela atual, sem nenhuma tela nova de autoatendimento — o escopo desta
   fase encolhe bastante (sem tela de "meu plano" com botão de ativar, só a
   página de aceite do convite). Me diga qual dos dois você quer.

## 4. Corte Avulso — sem mudança

Já funciona (`is_subscriber=False`, `walk_in_price()`). Não entra
`apps.finance`: continua um agendamento avulso em `apps.barbershop`, sem
`BillingProfile`. No perfil, "sem plano ativo" mostra um link pra marcar
corte avulso — reaproveita a tela de agendamento existente.

## 5. Fim do `is_subscriber` confiado pelo cliente

`AppointmentCreateSerializer` perde o campo `is_subscriber` — deixa de vir
do corpo da requisição. `BarbershopService.book()` passa a calcular
internamente: busca o `BillingProfile` ativo do `customer_id` via
`apps.finance` (import de serviço/repositório, sentido único —
`apps.barbershop` → `apps.finance`, sem ciclo); se ativo com plano
Associado ou Mensalista Barbearia, `is_subscriber=True` (cota 4, corte
grátis); senão `is_subscriber=False` (`walk_in_price()`, sem cota, sem
trava). `reschedule()` recalcula do mesmo jeito ao trocar de mês.

Isso é uma mudança de contrato de API (`is_subscriber` sai do payload de
criação) — os testes atuais de `apps/barbershop/tests/test_barbershop.py`
que mandam esse campo direto precisam ser reescritos pra montar o cenário
via `BillingProfile` em vez de mandar o boolean.

`SUBSCRIBER_MONTHLY_LIMIT` sobe de `3` para `4` (vale igual pros dois
planos — nenhum dos dois precisa de um limite próprio).

## 6. Notificações (`apps.notifications`, novo)

App novo e enxuto:

- `Notification` (tenant-scoped): `user`, `kind` (por ora só
  `finance_overdue`), `title`, `message`, `link` opcional, `read_at` nulo
  até lida, `created_at`.
- Disparo: dentro do `roll_all`/`roll_dues` diário, ao comparar o
  `financial_status` antes/depois de cada perfil — se piorou pra
  `due_soon`/`due_today`/`overdue`/`delinquent` (transição, não repetição
  diária do mesmo estado), cria uma notificação.
- Frontend: sino no topo com contador de não lidas + lista (dropdown ou
  página `/notificacoes`), marcar como lida ao abrir.
- Só o gatilho financeiro entra nesta fase — a estrutura é genérica o
  bastante pra outros módulos plugarem depois, mas não construo mais
  nenhum produtor agora (YAGNI).

## 7. Perfil do usuário

O card "Minha mensalidade" (`ProfilePage.tsx`) passa a mostrar qual plano
(Associado / Mensalista Barbearia) além da situação já existente, e ganha a
cota do mês (`X de 4 cortes usados`, via `subscriber_quota` já existente em
`BarbershopService`). Sem `BillingProfile` ativo, o card mostra "Sem plano
ativo" com um link pra marcar corte avulso.

## 8. Migração de dados

Os `BillingProfile` já ativos hoje (Fase 1, mensalidade única) recebem
`plan=ASSOCIADO` numa migração de dados — é o relacionamento que essas
pessoas já tinham. `Due`s já geradas **não mudam de valor** (preço
congelado no ato, mesmo princípio já usado em toda a base) — só as novas
`Due`s, geradas daqui pra frente, usam `plan_price()`.

## Fora de escopo (Fase 2)

- Trocar automaticamente de plano quando o posto muda — fica manual
  (admin ou usuário ajusta na mão).
- Editar valor dos planos pela UI — continuam via `.env`, mesmo padrão do
  `MEMBERSHIP_FEE` atual.
- Qualquer notificação além do financeiro vencendo/vencido.
- Mudar o mecanismo de pagamento do Corte Avulso (Pix) — já existe, não
  mexo.

## Fases de execução

1. **2a — Postos, Planos, Elegibilidade, Convite**: o núcleo; tudo dentro de
   `apps.accounts` + `apps.finance` + frontend correspondente.
2. **2b — Integração de cota com a Agenda**: `is_subscriber` server-side,
   limite 4, dependência `apps.barbershop` → `apps.finance`. Depende de 2a.
3. **2c — Notificações**: app novo, gatilho financeiro. Pode rodar em
   paralelo com 2b (não depende dela), mas depende de 2a existir
   (financial_status já reflete o plano certo).
