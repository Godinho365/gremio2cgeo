"""Base repository. Hides the ORM and enforces tenant isolation (RN-T1).

Services depend on repositories, never on the ORM directly.
"""
from __future__ import annotations

from typing import Generic, TypeVar
from uuid import UUID

from django.db import models

from core.context import get_current_tenant_id
from core.models import TenantScopedModel

M = TypeVar("M", bound=TenantScopedModel)


class TenantIsolationError(Exception):
    """No tenant bound to the current context while accessing scoped data."""


class BaseRepository(Generic[M]):
    model: type[M]

    def _require_tenant(self) -> UUID:
        tenant_id = get_current_tenant_id()
        if tenant_id is None:
            raise TenantIsolationError(
                f"No current tenant while accessing {self.model.__name__}."
            )
        return tenant_id

    def query(self) -> models.QuerySet[M]:
        """Base queryset: current tenant only, not soft-deleted."""
        self._require_tenant()
        return self.model.objects.for_current_tenant().alive()

    def get(self, pk: UUID | str) -> M:
        return self.query().get(pk=pk)

    def all(self) -> models.QuerySet[M]:
        return self.query()

    def create(self, **data: object) -> M:
        tenant_id = self._require_tenant()
        return self.model.objects.create(tenant_id=tenant_id, **data)

    def soft_delete(self, instance: M) -> None:
        from django.utils import timezone

        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at", "updated_at"])
