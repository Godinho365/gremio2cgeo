"""AssetService — business rules for the Asset domain (RN-A1..A4).

Views call this; it never touches HTTP. See docs/modulos/patrimonio.md.
"""
from __future__ import annotations

from uuid import UUID

from django.db import transaction

from core import audit
from core.exceptions import BusinessRuleError
from core.services import BaseService

from .models import Asset
from .repositories import AssetRepository


class AssetService(BaseService):
    def __init__(self, repository: AssetRepository | None = None) -> None:
        self.repository = repository or AssetRepository()

    @transaction.atomic
    def create_asset(
        self, *, asset_tag: str, name: str, actor_id: UUID | None = None, **fields: object
    ) -> Asset:
        # RN-A1: asset_tag unique per tenant.
        if self.repository.tag_exists(asset_tag):
            raise BusinessRuleError(
                f"asset_tag '{asset_tag}' já existe.", code="asset_tag_duplicate"
            )
        asset = self.repository.create(asset_tag=asset_tag, name=name, **fields)
        audit.record(
            action="asset.created",
            entity_type="Asset",
            entity_id=asset.id,
            actor_id=actor_id,
            diff={"asset_tag": asset_tag, "name": name},
        )
        return asset
