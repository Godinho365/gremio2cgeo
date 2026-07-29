"""Base DRF viewsets.

- ``TenantScopedViewSet`` binds the tenant context after authentication
  (DRF authenticates in the view, not middleware).
- ``TenantCrudViewSet`` adds tenant-safe CRUD for simple catalog models
  (no domain rules). Models with business rules go through a Service instead.
Views translate HTTP <-> data; they hold no business logic.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils import timezone
from rest_framework import viewsets

from core.context import get_current_tenant_id, set_current_tenant_id

if TYPE_CHECKING:
    from django.db import models
    from rest_framework.request import Request
    from rest_framework.serializers import BaseSerializer


class TenantScopedViewSet(viewsets.ModelViewSet):
    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        set_current_tenant_id(getattr(request.user, "tenant_id", None))


class TenantCrudViewSet(TenantScopedViewSet):
    """Generic CRUD scoped to the current tenant, with soft delete."""

    def get_queryset(self) -> models.QuerySet:  # type: ignore[override]
        model = self.serializer_class.Meta.model  # type: ignore[union-attr]
        return model.objects.for_current_tenant().alive().order_by("-created_at")

    def perform_create(self, serializer: BaseSerializer) -> None:
        serializer.save(
            tenant_id=get_current_tenant_id(),
            created_by=self.request.user if self.request.user.is_authenticated else None,
        )

    def perform_destroy(self, instance: models.Model) -> None:
        instance.deleted_at = timezone.now()  # type: ignore[attr-defined]
        instance.save(update_fields=["deleted_at", "updated_at"])
