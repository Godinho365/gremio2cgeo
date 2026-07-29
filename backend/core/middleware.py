"""Resolves the current tenant from the authenticated user and binds it to the
request-scoped context (see core.context). This is the enforcement point for
RN-T1: repositories read the tenant from the context, not from client input.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.context import set_current_tenant_id

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponse


class TenantMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        tenant_id = None
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            tenant_id = getattr(user, "tenant_id", None)
        set_current_tenant_id(tenant_id)
        try:
            return self.get_response(request)
        finally:
            set_current_tenant_id(None)
