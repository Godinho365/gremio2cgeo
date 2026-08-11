"""AssetService — business rules for the Asset domain (RN-A1..A4).

Views call this; it never touches HTTP. See docs/modulos/patrimonio.md.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from django.db import IntegrityError, transaction

from core import audit
from core.context import get_current_tenant_id
from core.exceptions import BusinessRuleError
from core.services import BaseService

from .models import Asset
from .repositories import AssetRepository

_MAX_TAG_RETRIES = 5


class AssetService(BaseService):
    def __init__(self, repository: AssetRepository | None = None) -> None:
        self.repository = repository or AssetRepository()

    def _next_tag(self, tenant_id: UUID) -> str:
        """PAT-{year}-{seq} sequential per tenant/year (RN-A1).

        TODO(concurrency): replace count-based seq with a per-tenant sequence
        table; for now the unique constraint + retry loop guards collisions.
        """
        year = date.today().year
        prefix = f"PAT-{year}-"
        count = Asset.objects.filter(tenant_id=tenant_id, asset_tag__startswith=prefix).count()
        return f"{prefix}{count + 1:06d}"

    @transaction.atomic
    def create_asset(
        self,
        *,
        name: str,
        asset_tag: str | None = None,
        actor_id: UUID | None = None,
        **fields: object,
    ) -> Asset:
        tenant_id = get_current_tenant_id()
        if tenant_id is None:
            raise BusinessRuleError("Sem tenant no contexto.", code="no_tenant")

        # Explicit tag: must be unique (RN-A1).
        if asset_tag:
            if self.repository.tag_exists(asset_tag):
                raise BusinessRuleError(
                    f"asset_tag '{asset_tag}' já existe.", code="asset_tag_duplicate"
                )
            return self._persist(tenant_id, asset_tag, name, actor_id, fields)

        # Auto-generated tag: retry on race against the unique constraint.
        for _ in range(_MAX_TAG_RETRIES):
            candidate = self._next_tag(tenant_id)
            try:
                with transaction.atomic():
                    return self._persist(tenant_id, candidate, name, actor_id, fields)
            except IntegrityError:
                continue
        raise BusinessRuleError("Não foi possível gerar asset_tag.", code="asset_tag_generation")

    @transaction.atomic
    def delete_asset(self, *, asset: Asset, actor_id: UUID | None = None) -> None:
        """Exclui o bem do acervo (soft delete — o histórico de cautelas continua).

        Um bem que está com alguém não sai do acervo: a entrega tem de ser
        registrada antes, senão o termo de responsabilidade fica órfão.
        """
        from apps.custody.models import OPEN_CUSTODY_STATUSES, Custody

        em_aberto = Custody.objects.filter(
            asset_id=asset.pk, status__in=OPEN_CUSTODY_STATUSES, deleted_at__isnull=True
        ).exists()
        if em_aberto:
            raise BusinessRuleError(
                "Este bem está cautelado. Registre a entrega antes de excluir.",
                code="asset_in_custody",
            )

        self.repository.soft_delete(asset)
        audit.record(
            action="asset.deleted",
            entity_type="Asset",
            entity_id=asset.pk,
            actor_id=actor_id,
            diff={"asset_tag": asset.asset_tag, "name": asset.name},
        )

    def _persist(
        self,
        tenant_id: UUID,
        asset_tag: str,
        name: str,
        actor_id: UUID | None,
        fields: dict[str, object],
    ) -> Asset:
        asset = self.repository.create(asset_tag=asset_tag, name=name, **fields)
        audit.record(
            action="asset.created",
            entity_type="Asset",
            entity_id=asset.id,
            actor_id=actor_id,
            diff={"asset_tag": asset_tag, "name": name},
        )
        return asset
