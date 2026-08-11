"""User data access, scoped to the current tenant (RN-T1).

User isn't a TenantScopedModel (it extends AbstractUser), so tenant filtering
is applied explicitly here.
"""
from __future__ import annotations

from django.db import models

from core.context import get_current_tenant_id

from .models import Role, User


class UserRepository:
    def query(self) -> models.QuerySet[User]:
        tenant_id = get_current_tenant_id()
        if tenant_id is None:
            return User.objects.none()
        return User.objects.filter(tenant_id=tenant_id)

    def all(self) -> models.QuerySet[User]:
        return self.query().order_by("username")

    def username_taken(self, username: str, exclude_id: object = None) -> bool:
        # username is globally unique in Django's default auth (see TODO in models).
        qs = User.objects.filter(username=username)
        return qs.exclude(pk=exclude_id).exists() if exclude_id else qs.exists()

    def email_taken(self, email: str, exclude_id: object = None) -> bool:
        qs = User.objects.filter(email__iexact=email)
        return qs.exclude(pk=exclude_id).exists() if exclude_id else qs.exists()

    def cpf_taken(self, cpf: str, exclude_id: object = None) -> bool:
        qs = User.objects.filter(cpf=cpf)
        return qs.exclude(pk=exclude_id).exists() if exclude_id else qs.exists()


class RoleRepository:
    def by_codes(self, codes: list[str]) -> models.QuerySet[Role]:
        return Role.objects.filter(code__in=codes)
