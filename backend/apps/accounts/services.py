"""Auth/account business logic. See docs/modulos + personas-perfis.md.

Covers org onboarding (tenant + first admin) and tenant-scoped user management.
"""
from __future__ import annotations

from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils.text import slugify

from core import audit
from core.context import use_tenant
from core.exceptions import BusinessRuleError
from core.models import Tenant
from core.services import BaseService

from .models import RoleCode, User
from .repositories import RoleRepository, UserRepository


class UserService(BaseService):
    def __init__(
        self,
        users: UserRepository | None = None,
        roles: RoleRepository | None = None,
    ) -> None:
        self.users = users or UserRepository()
        self.roles = roles or RoleRepository()

    @transaction.atomic
    def create_user(
        self,
        *,
        username: str,
        password: str,
        email: str = "",
        role_codes: list[str] | None = None,
        tenant_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> User:
        if self.users.username_taken(username):
            raise BusinessRuleError("Nome de usuário já existe.", code="username_taken")

        try:
            user = User(username=username, email=email, tenant_id=tenant_id)
            user.set_password(password)
            user.save()
        except IntegrityError as exc:  # pragma: no cover - defensive
            raise BusinessRuleError("Não foi possível criar o usuário.") from exc

        if role_codes:
            user.roles.set(self.roles.by_codes(role_codes))

        audit.record(
            action="user.created",
            entity_type="User",
            entity_id=user.id,
            actor_id=actor_id,
            diff={"username": username, "roles": role_codes or []},
        )
        return user


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
