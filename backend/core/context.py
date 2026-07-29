"""Request-scoped tenant context.

Stored in a context variable so services/repositories can enforce tenant
isolation without threading the tenant through every call signature.
Set by ``core.middleware.TenantMiddleware`` on each request.
"""
from __future__ import annotations

import contextlib
from contextvars import ContextVar
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from collections.abc import Iterator

_current_tenant_id: ContextVar[UUID | None] = ContextVar("current_tenant_id", default=None)


def set_current_tenant_id(tenant_id: UUID | None) -> None:
    _current_tenant_id.set(tenant_id)


def get_current_tenant_id() -> UUID | None:
    return _current_tenant_id.get()


@contextlib.contextmanager
def use_tenant(tenant_id: UUID | None) -> Iterator[None]:
    """Temporarily bind a tenant (useful in tasks, tests, management commands)."""
    token = _current_tenant_id.set(tenant_id)
    try:
        yield
    finally:
        _current_tenant_id.reset(token)
