# Perfil "Cliente da Barbearia" — Design

Data: 2026-08-29
Status: aprovado

## Contexto

O sistema é multi-módulo (Patrimônio + Barbearia). Hoje, todo usuário autenticado
sem perfil de staff (`admin`/`director`/`inventory`/`auditor`) e sem o perfil
`barbershop` (administrador da barbearia) enxerga automaticamente três telas:
Catálogo e Agenda (reserva de bens patrimoniais) e Barbearia. Isso vale tanto
pra quem se cadastra publicamente (`RoleCode.USER`) quanto para qualquer papel
futuro sem restrição explícita — porque os itens de menu/rotas de Catálogo e
Agenda hoje não declaram `roles`, ou seja, são abertos por padrão.

Precisamos de um perfil que só tenha acesso à Barbearia: cria/vê/cancela os
próprios agendamentos de corte, e nada do módulo Patrimônio.

## Papel novo

`RoleCode.BARBERSHOP_CLIENT = "barbershop_client"`, label **"Cliente da
Barbearia"**. É distinto do `RoleCode.BARBERSHOP` existente ("Administrador da
Barbearia", que cadastra barbeiros e define horários — ver
`_MANAGE_ROLES` em `apps/barbershop/api/views.py`).

Atribuição: só pelo admin, pela tela de Usuários (`UsersPage` → `ROLES`). O
autocadastro público (`/signup`) não muda — continua criando `RoleCode.USER`.

Uso pretendido: perfil exclusivo, não combinar com outros papéis. O bloqueio
de backend (`ExcludesRoles`) reage à simples presença do papel
`barbershop_client` no usuário, independente de ele ter outros papéis também —
então alguém com `admin` + `barbershop_client` ainda tomaria 403 nos
endpoints de Patrimônio gateados por `ExcludesRoles`, mesmo sendo admin. Não
há necessidade de suportar esse acúmulo agora; se surgir, é um ajuste local
nos poucos pontos que usam `ExcludesRoles`.

## Backend

### 1. Modelo e seed

- `apps/accounts/models.py`: adicionar `BARBERSHOP_CLIENT` ao `RoleCode`.
- Nova migration `apps/accounts/migrations/000N_seed_barbershop_client_role.py`,
  mesmo padrão de `0006_seed_barbershop_role.py` (RunPython seed/unseed via
  `Role.objects.update_or_create`).

### 2. Permissão genérica `ExcludesRoles`

Em `core/permissions.py`, ao lado de `HasAnyRole`, uma permissão simétrica:

```python
class ExcludesRoles(BasePermission):
    message = "Este perfil não tem acesso a este recurso."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        excluded = tuple(getattr(view, "excluded_roles", ()))
        if not excluded:
            return True
        return not user.roles.filter(code__in=excluded).exists()
```

Segue o mesmo contrato de `HasAnyRole` (view declara a lista via atributo,
`core` não importa `RoleCode` — mantém a camada `core` agnóstica de app).

### 3. Aplicação nos endpoints do módulo Patrimônio

Todos com `excluded_roles = (RoleCode.BARBERSHOP_CLIENT,)`:

- `apps/assets/api/views.py::AssetViewSet` — no `get_permissions`, ramo de
  leitura (`GET/HEAD/OPTIONS`): `[IsAuthenticated(), ExcludesRoles()]`.
- `apps/scheduling/api/views.py::BookingViewSet` — `permission_classes =
  [IsAuthenticated, ExcludesRoles]` (cobre list/retrieve/create/destroy/
  approve/cancel).
- `apps/scheduling/api/views.py::AvailabilityViewSet` — no `get_permissions`,
  ramo de leitura: `[IsAuthenticated(), ExcludesRoles()]`.

Fora do escopo (permanecem abertos a qualquer autenticado, sem mudança):
`CategoryViewSet`, `LocationViewSet`, `SupplierViewSet`, `AcquisitionViewSet`
— são metadados de apoio ao catálogo, não a ação de reservar em si.

## Frontend

### 1. Catálogo de perfis

- `features/accounts/api.ts::ROLES` — adicionar
  `{ value: "barbershop_client", label: "Cliente da Barbearia" }` (entra em
  `ROLE_LABEL` automaticamente).

### 2. Novo grupo de papéis e `homePath`

Em `auth/roles.ts`:

```ts
/** Quem enxerga Catálogo e Agenda do módulo Patrimônio. */
export const PATRIMONIO_ROLES = [...STAFF_ROLES, "user"];
```

`homePath()` passa a considerar três casos (staff/barbershop-admin → escolhe
módulo; quem tem acesso a Patrimônio → `/catalogo`; senão → `/barbearia`):

```ts
export function homePath(user: CurrentUser | null): string {
  if (canChooseModule(user)) return "/modulos";
  if (hasAnyRole(user, PATRIMONIO_ROLES)) return "/catalogo";
  return "/barbearia";
}
```

### 3. Menu (`components/Layout.tsx`)

Os itens `Catálogo` e `Agenda` (módulo `patrimonio`) passam a declarar
`roles: PATRIMONIO_ROLES` (hoje não têm `roles`, logo aparecem pra todo mundo
autenticado).

### 4. Rotas (`App.tsx`)

`/catalogo` e `/agenda` passam a ficar dentro de um
`<Route element={<RequireRole roles={PATRIMONIO_ROLES} />}>`, mesmo padrão já
usado para `/patrimonio`, `/cautelas`, `/inventario` etc. Quem não tem o papel
e tentar acessar a URL direto é redirecionado por `RequireRole` para
`homePath(user)` — que agora resolve corretamente para `/barbearia` nesse
caso, sem loop.

## Testes

- Backend (`apps/accounts/tests` ou `apps/scheduling/tests`/`apps/assets/tests`,
  o que fizer mais sentido ao implementar): usuário só com `barbershop_client`
  recebe 403 em `GET /assets`, `POST /bookings`, `GET /availability`; e
  recebe 201 normalmente em `POST` de agendamento da barbearia
  (`/barbershop/appointments` ou nome equivalente do endpoint).
- Frontend: sem suíte de UI automatizada no projeto hoje. Verificação manual
  no navegador após implementar: login como cliente da barbearia → aterrissa
  em `/barbearia`; menu mostra só Barbearia; acesso direto a `/catalogo` e
  `/agenda` redireciona de volta.

## Fora de escopo

- Autocadastro público não ganha opção de escolher esse perfil.
- Categoria/Local/Fornecedor/Aquisição não são bloqueados no backend.
- Cautelas/Inventário/Financeiro já são inacessíveis pra esse perfil (herda o
  comportamento de `STAFF_ROLES` que já existe) — nenhuma mudança necessária
  aí.
