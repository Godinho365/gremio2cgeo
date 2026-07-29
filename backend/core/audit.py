"""Helper to record audit entries (RN-X1)."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from core.context import get_current_tenant_id
from core.models import AuditLog


def record(
    *,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    actor_id: UUID | None = None,
    diff: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        raise RuntimeError("audit.record requires a current tenant in context.")
    return AuditLog.objects.create(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        diff=diff or {},
        ip=ip,
    )
