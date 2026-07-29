"""Base DRF viewset that binds the tenant context after authentication.

DRF authenticates inside the view (not middleware), so we set the tenant in
``initial()`` — after ``request.user`` is resolved but before the handler runs.
Views translate HTTP <-> service; they hold no business logic.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework import viewsets

from core.context import set_current_tenant_id

if TYPE_CHECKING:
    from rest_framework.request import Request


class TenantScopedViewSet(viewsets.ModelViewSet):
    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        tenant_id = getattr(request.user, "tenant_id", None)
        set_current_tenant_id(tenant_id)
