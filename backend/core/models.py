"""Base models: UUID PK, timestamps, soft delete, tenant scoping, audit log.

See docs/dominio/entidades.md ("Regras transversais") and RN-T1/RN-A4.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from core.context import get_current_tenant_id


def new_uuid() -> uuid.UUID:
    # TODO(ADR-0003): migrate to UUIDv7 (ordenável). uuid4 by now.
    return uuid.uuid4()


class TimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=new_uuid, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class Tenant(TimeStampedModel):
    """Root of data isolation (the SaaS customer organization)."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "tenant"

    def __str__(self) -> str:
        return self.name


class TenantScopedQuerySet(models.QuerySet):
    def for_current_tenant(self) -> TenantScopedQuerySet:
        tenant_id = get_current_tenant_id()
        if tenant_id is None:
            return self.none()
        return self.filter(tenant_id=tenant_id)

    def alive(self) -> TenantScopedQuerySet:
        return self.filter(deleted_at__isnull=True)


class TenantManager(models.Manager.from_queryset(TenantScopedQuerySet)):  # type: ignore[misc]
    pass


class TenantScopedModel(TimeStampedModel):
    """Every business entity inherits this. Always carries a tenant. (RN-T1)"""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="+")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    objects = TenantManager()

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["tenant"])]


class AuditLog(TimeStampedModel):
    """Append-only trail of sensitive actions (RN-X1). Never updated/deleted."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="+")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.UUIDField(null=True, blank=True)
    diff = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "audit_log"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} {self.entity_type}:{self.entity_id}"
