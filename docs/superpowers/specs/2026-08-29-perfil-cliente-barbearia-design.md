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

Atribuição: pelo admin, na tela de Usuários (`UsersPage` → `ROLES`); ou
automaticamente, pela regra de posto/graduação abaixo (vale inclusive no
autocadastro público). Fora dessa regra de posto, o autocadastro continua
criando `RoleCode.USER`.

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

## Regra: posto/graduação Sd ou Cb força o perfil

Praças de posto **Sd** (Soldado) ou **Cb** (Cabo) só têm o perfil **Cliente da
Barbearia** — em qualquer lugar do sistema que grave posto/graduação e/ou
perfil, o backend força `role_codes = [BARBERSHOP_CLIENT]` e descarta
qualquer outro perfil que tivesse sido escolhido. Regra dura, sem exceção:
não é possível ter Sd/Cb combinado com `admin`, `director`, `user` etc.

### Backend (`apps/accounts/services.py::UserService`)

Helper único, reaproveitado nos três pontos de entrada:

```python
_BARBERSHOP_ONLY_RANKS = {"Sd", "Cb"}

def _forced_roles_for_rank(self, posto_graduacao: str) -> list[str] | None:
    """Praças (Sd/Cb) só têm o perfil Cliente da Barbearia."""
    if posto_graduacao in _BARBERSHOP_ONLY_RANKS:
        return [RoleCode.BARBERSHOP_CLIENT]
    return None
```

- `create_user`: calcula `effective_role_codes = self._forced_roles_for_rank(posto_graduacao) or role_codes`
  antes de `user.roles.set(...)` e antes de gravar o `audit.record`. Como
  `self_register` chama `create_user`, o autocadastro público herda a regra
  de graça — sem tocar em `self_register`.
- `update_user`: calcula o posto/graduação *efetivo* (`fields.get("posto_graduacao", user.posto_graduacao)`)
  e usa `_forced_roles_for_rank` sobre ele para decidir `effective_role_codes`,
  mesmo que `role_codes` não tenha sido passado nesta chamada — ou seja, só
  trocar o posto pra Sd/Cb (sem tocar no seletor de perfil) já basta pra
  forçar a troca. A checagem existente de autoproteção ("você não pode
  remover o próprio perfil de administrador") passa a olhar
  `effective_role_codes` em vez do `role_codes` bruto — então um admin não
  consegue se auto-rebaixar por essa via também: mudar o próprio posto para
  Sd/Cb sendo o único admin dá o mesmo erro de hoje.
- `update_profile` (edição do próprio perfil, sem escolha de perfil de acesso
  nessa tela): se o posto/graduação mudar para Sd/Cb nesta chamada, aplica
  `user.roles.set(...)` com o perfil forçado e inclui `"roles"` no diff do
  `AuditLog`, junto com os demais campos alterados.

### Frontend (`UsersPage.tsx`)

No formulário de usuário (`UserFormModal`), quando `form.posto_graduacao` é
`"Sd"` ou `"Cb"`: o `<select>` de Perfil passa a mostrar e travar em "Cliente
da Barbearia" (mesmo tratamento visual que já existe para `disabled={isSelf}`),
com uma dica no lugar do `ROLE_HINT` explicando a regra — assim o admin vê
antes de salvar o que vai valer, em vez de escolher um perfil que será
sobrescrito silenciosamente.

`SignupPage.tsx` não muda: já não expõe seletor de perfil (o autocadastro
sempre foi implícito), então o comportamento novo é só um efeito de bastidor
do backend.

### Dados já existentes

Sem migração de backfill: usuários que já têm posto Sd/Cb com outro perfil
(se houver) continuam como estão até serem salvos de novo (edição pelo admin
ou pela própria pessoa dispara a regra na próxima gravação). Fora de escopo
por ora — sinalize se quiser um backfill.

## Testes

- Backend (`apps/accounts/tests` ou `apps/scheduling/tests`/`apps/assets/tests`,
  o que fizer mais sentido ao implementar): usuário só com `barbershop_client`
  recebe 403 em `GET /assets`, `POST /bookings`, `GET /availability`; e
  recebe 201 normalmente em `POST` de agendamento da barbearia
  (`/barbershop/appointments` ou nome equivalente do endpoint).
- Backend (`apps/accounts/tests/test_auth_and_rbac.py`): `create_user`/
  `update_user`/`update_profile`/`self_register` com posto Sd ou Cb sempre
  resultam em `roles == [barbershop_client]`, mesmo pedindo outro
  `role_codes` explicitamente; e o guard de autoproteção do admin continua
  funcionando quando é a mudança de posto que gera a tentativa de
  autorrebaixamento.
- Frontend: sem suíte de UI automatizada no projeto hoje. Verificação manual
  no navegador após implementar: login como cliente da barbearia → aterrissa
  em `/barbearia`; menu mostra só Barbearia; acesso direto a `/catalogo` e
  `/agenda` redireciona de volta; no formulário de Usuários, selecionar Sd ou
  Cb trava o campo Perfil em "Cliente da Barbearia".

## Fora de escopo

- Categoria/Local/Fornecedor/Aquisição não são bloqueados no backend.
- Cautelas/Inventário/Financeiro já são inacessíveis pra esse perfil (herda o
  comportamento de `STAFF_ROLES` que já existe) — nenhuma mudança necessária
  aí.
- Backfill de usuários existentes com posto Sd/Cb e perfil divergente.
