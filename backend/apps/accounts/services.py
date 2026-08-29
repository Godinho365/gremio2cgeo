"""Auth/account business logic. See docs/modulos + personas-perfis.md.

Covers org onboarding (tenant + first admin) and tenant-scoped user management.
"""
from __future__ import annotations

from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils.text import slugify

from core import audit
from core.context import use_tenant
from core.exceptions import BusinessRuleError
from core.models import Tenant
from core.services import BaseService

from .models import RoleCode, User
from .repositories import RoleRepository, UserRepository


class UserService(BaseService):
    _BARBERSHOP_ONLY_RANKS = frozenset({"Sd", "Cb"})

    def __init__(
        self,
        users: UserRepository | None = None,
        roles: RoleRepository | None = None,
    ) -> None:
        self.users = users or UserRepository()
        self.roles = roles or RoleRepository()

    def _unique_username(self, base: str) -> str:
        """Login gerado para quem não tem acesso (só existe para constar no histórico)."""
        slug = slugify(base) or "convidado"
        candidate = slug
        suffix = 2
        while self.users.username_taken(candidate):
            candidate = f"{slug}-{suffix}"
            suffix += 1
        return candidate

    def _forced_roles_for_rank(self, posto_graduacao: str) -> list[str] | None:
        """Praças (Sd/Cb) só têm o perfil Cliente da Barbearia — regra de hierarquia."""
        if posto_graduacao in self._BARBERSHOP_ONLY_RANKS:
            return [RoleCode.BARBERSHOP_CLIENT]
        return None

    @transaction.atomic
    def create_user(
        self,
        *,
        username: str = "",
        password: str = "",
        email: str = "",
        nome_guerra: str = "",
        posto_graduacao: str = "",
        full_name: str = "",
        cpf: str = "",
        birth_date: object = None,
        phone: str = "",
        is_active: bool = True,
        role_codes: list[str] | None = None,
        tenant_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> User:
        # Quem entra no sistema precisa de senha; quem é só cadastro (sem acesso), não.
        if is_active and not password:
            raise BusinessRuleError(
                "Usuário com acesso precisa de senha.", code="password_required"
            )
        if not username:
            username = self._unique_username(full_name or nome_guerra or email)
        if self.users.username_taken(username):
            raise BusinessRuleError("Nome de usuário já existe.", code="username_taken")

        try:
            user = User(
                username=username,
                email=email,
                tenant_id=tenant_id,
                nome_guerra=nome_guerra,
                posto_graduacao=posto_graduacao,
                full_name=full_name,
                cpf=cpf,
                birth_date=birth_date,
                phone=phone,
                is_active=is_active,
            )
            if password:
                user.set_password(password)
            else:
                user.set_unusable_password()
            user.save()
        except IntegrityError as exc:  # pragma: no cover - defensive
            raise BusinessRuleError("Não foi possível criar o usuário.") from exc

        effective_role_codes = self._forced_roles_for_rank(posto_graduacao) or role_codes
        if effective_role_codes:
            user.roles.set(self.roles.by_codes(effective_role_codes))

        audit.record(
            action="user.created",
            entity_type="User",
            entity_id=user.id,
            actor_id=actor_id,
            diff={
                "username": username,
                "roles": effective_role_codes or [],
                "is_active": is_active,
            },
        )
        return user

    @transaction.atomic
    def update_user(
        self,
        *,
        user: User,
        actor: User,
        role_codes: list[str] | None = None,
        **fields: object,
    ) -> User:
        """Edição de usuário pelo administrador (RBAC, dados cadastrais e acesso)."""
        is_self = user.pk == actor.pk

        # Sd/Cb só têm o perfil Cliente da Barbearia — vale mesmo que só o
        # posto tenha mudado nesta chamada, sem pedir troca de perfil.
        effective_posto = fields.get("posto_graduacao", user.posto_graduacao)
        forced_roles = self._forced_roles_for_rank(
            effective_posto if isinstance(effective_posto, str) else user.posto_graduacao
        )
        effective_role_codes = forced_roles if forced_roles is not None else role_codes

        if (
            effective_role_codes is not None
            and is_self
            and RoleCode.ADMIN not in effective_role_codes
        ):
            raise BusinessRuleError(
                "Você não pode remover o próprio perfil de administrador.",
                code="cannot_demote_self",
            )
        if fields.get("is_active") is False and is_self:
            raise BusinessRuleError(
                "Você não pode remover o próprio acesso.", code="cannot_deactivate_self"
            )

        email = fields.get("email")
        if isinstance(email, str) and email:
            normalized = email.strip().lower()
            if self.users.email_taken(normalized, exclude_id=user.pk):
                raise BusinessRuleError(
                    "Já existe um cadastro com este e-mail.", code="email_taken"
                )
            fields["email"] = normalized
        username = fields.get("username")
        if isinstance(username, str) and username:
            if self.users.username_taken(username, exclude_id=user.pk):
                raise BusinessRuleError("Nome de usuário já existe.", code="username_taken")
        cpf = fields.get("cpf")
        if isinstance(cpf, str) and cpf and self.users.cpf_taken(cpf, exclude_id=user.pk):
            raise BusinessRuleError("Já existe um cadastro com este CPF.", code="cpf_taken")

        changed = {f: v for f, v in fields.items() if getattr(user, f) != v}
        if changed:
            for field, value in changed.items():
                setattr(user, field, value)
            user.save(update_fields=list(changed))
        if effective_role_codes is not None:
            user.roles.set(self.roles.by_codes(effective_role_codes))
            changed["roles"] = effective_role_codes

        if changed:
            audit.record(
                action="user.updated",
                entity_type="User",
                entity_id=user.pk,
                actor_id=actor.pk,
                diff={k: str(v) for k, v in changed.items()},
            )
        return user

    @transaction.atomic
    def delete_user(self, *, user: User, actor: User) -> None:
        """Apaga o cadastro. Quem já tem histórico não é apagado — perde o acesso.

        Reserva, cautela e auditoria apontam para o usuário; apagar quem já
        movimentou bem destruiria o rastro de quem respondeu pelo quê.
        """
        if user.pk == actor.pk:
            raise BusinessRuleError(
                "Você não pode excluir o próprio cadastro.", code="cannot_delete_self"
            )
        if user.has_role(RoleCode.ADMIN):
            outros_admins = (
                User.objects.filter(tenant_id=user.tenant_id, roles__code=RoleCode.ADMIN)
                .exclude(pk=user.pk)
                .exists()
            )
            if not outros_admins:
                raise BusinessRuleError(
                    "Este é o único administrador. Promova outro antes de excluir.",
                    code="last_admin",
                )

        try:
            with transaction.atomic():
                user.delete()
        except ProtectedError as exc:
            raise BusinessRuleError(
                "Este usuário tem reservas ou cautelas registradas e não pode ser "
                "excluído. Remova o acesso dele em vez disso.",
                code="user_has_history",
            ) from exc

        audit.record(
            action="user.deleted",
            entity_type="User",
            entity_id=user.pk,
            actor_id=actor.pk,
            diff={"username": user.username, "display_name": user.display_name},
        )

    @transaction.atomic
    def reset_password(self, *, user: User, actor: User, new_password: str) -> None:
        """Administrador redefine a senha de outro usuário (ex.: senha esquecida)."""
        user.set_password(new_password)
        user.save(update_fields=["password"])
        audit.record(
            action="user.password_reset",
            entity_type="User",
            entity_id=user.pk,
            actor_id=actor.pk,
        )

    @transaction.atomic
    def update_profile(
        self,
        *,
        user: User,
        email: str | None = None,
        phone: str | None = None,
        nome_guerra: str | None = None,
        posto_graduacao: str | None = None,
    ) -> User:
        """Edição do próprio perfil: contato, nome de guerra e posto/graduação.

        Posto/graduação entra aqui porque muda com promoção, e é a própria
        pessoa quem sabe quando isso acontece. O que continua com a
        administração é o que identifica a pessoa: nome, CPF, nascimento.

        Quando o login é o próprio e-mail, `username` acompanha a troca.
        """
        updates: dict[str, str] = {}

        if email is not None:
            normalized = email.strip().lower()
            if not normalized:
                raise BusinessRuleError("O e-mail é obrigatório.", code="email_required")
            if normalized != (user.email or "").lower():
                if self.users.email_taken(normalized, exclude_id=user.pk):
                    raise BusinessRuleError(
                        "Já existe um cadastro com este e-mail.", code="email_taken"
                    )
                if self.users.username_taken(normalized, exclude_id=user.pk):
                    raise BusinessRuleError(
                        "Já existe um usuário com este e-mail.", code="username_taken"
                    )
                updates["email"] = normalized
                if user.username.lower() == (user.email or "").lower():
                    updates["username"] = normalized

        if phone is not None:
            updates["phone"] = phone.strip()
        if nome_guerra is not None:
            updates["nome_guerra"] = nome_guerra.strip()
        if posto_graduacao is not None:
            updates["posto_graduacao"] = posto_graduacao.strip()

        changed: dict[str, object] = {
            f: v for f, v in updates.items() if getattr(user, f) != v
        }
        if not changed:
            return user

        forced_roles = None
        if "posto_graduacao" in changed:
            posto_value = changed["posto_graduacao"]
            forced_roles = self._forced_roles_for_rank(
                posto_value if isinstance(posto_value, str) else user.posto_graduacao
            )
            if (
                forced_roles is not None
                and user.has_role(RoleCode.ADMIN)
                and RoleCode.ADMIN not in forced_roles
            ):
                raise BusinessRuleError(
                    "Você não pode remover o próprio perfil de administrador.",
                    code="cannot_demote_self",
                )

        for field, value in changed.items():
            setattr(user, field, value)
        user.save(update_fields=list(changed))

        if forced_roles is not None:
            user.roles.set(self.roles.by_codes(forced_roles))
            changed["roles"] = forced_roles

        audit.record(
            action="user.profile_updated",
            entity_type="User",
            entity_id=user.pk,
            actor_id=user.pk,
            diff=changed,
        )
        return user

    @transaction.atomic
    def change_password(self, *, user: User, current_password: str, new_password: str) -> None:
        """Troca de senha pelo próprio usuário — exige a senha atual."""
        if not user.check_password(current_password):
            raise BusinessRuleError("Senha atual incorreta.", code="invalid_password")
        if current_password == new_password:
            raise BusinessRuleError(
                "A nova senha deve ser diferente da atual.", code="password_unchanged"
            )
        user.set_password(new_password)
        user.save(update_fields=["password"])
        audit.record(
            action="user.password_changed",
            entity_type="User",
            entity_id=user.pk,
            actor_id=user.pk,
        )

    @transaction.atomic
    def self_register(
        self,
        *,
        full_name: str,
        nome_guerra: str,
        posto_graduacao: str,
        cpf: str,
        birth_date: object,
        email: str,
        phone: str,
        password: str,
    ) -> User:
        """Auto-cadastro público: cria um usuário comum, já ativo, na organização."""
        tenant = Tenant.objects.filter(is_active=True).order_by("created_at").first()
        if tenant is None:
            raise BusinessRuleError(
                "Nenhuma organização disponível para cadastro.", code="no_org"
            )
        with use_tenant(tenant.id):
            return self.create_user(
                username=email,  # login por e-mail
                password=password,
                email=email,
                full_name=full_name,
                nome_guerra=nome_guerra,
                posto_graduacao=posto_graduacao,
                cpf=cpf,
                birth_date=birth_date,
                phone=phone,
                role_codes=[RoleCode.USER],
                tenant_id=tenant.id,
            )


class OnboardingService(BaseService):
    """Public org sign-up: creates a Tenant and its first Administrador."""

    def __init__(self, users: UserService | None = None) -> None:
        self.users = users or UserService()

    @transaction.atomic
    def create_organization(
        self,
        *,
        org_name: str,
        admin_username: str,
        admin_password: str,
        admin_email: str = "",
    ) -> tuple[Tenant, User]:
        slug = slugify(org_name)
        if Tenant.objects.filter(slug=slug).exists():
            raise BusinessRuleError("Já existe uma organização com esse nome.", code="org_exists")

        tenant = Tenant.objects.create(name=org_name, slug=slug)
        with use_tenant(tenant.id):
            admin = self.users.create_user(
                username=admin_username,
                password=admin_password,
                email=admin_email,
                role_codes=[RoleCode.ADMIN],
                tenant_id=tenant.id,
            )
        return tenant, admin
