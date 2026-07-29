"""User + Role. See docs/produto/personas-perfis.md.

The User belongs to a Tenant (multi-tenant root). RBAC via Role (M2M).
Login stays username-based for now; TODO(ADR): switch to email login.
"""
from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models import Tenant, TimeStampedModel, new_uuid


class RoleCode(models.TextChoices):
    ADMIN = "admin", "Administrador"
    DIRECTOR = "director", "Diretor(a) Patrimonial"
    INVENTORY = "inventory", "Inventariante"
    USER = "user", "Usuário"
    AUDITOR = "auditor", "Auditor"


class Role(TimeStampedModel):
    code = models.CharField(max_length=20, choices=RoleCode.choices, unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "role"

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=new_uuid, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="users", null=True, blank=True
    )
    roles = models.ManyToManyField(Role, related_name="users", blank=True)

    class Meta:
        db_table = "user"

    def has_role(self, code: str) -> bool:
        return self.roles.filter(code=code).exists()
