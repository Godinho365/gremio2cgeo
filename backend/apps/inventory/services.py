"""InventoryService — abertura, conferência e fechamento (Art.30 b, RN-I1..I3)."""
from __future__ import annotations

from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.assets.models import Asset, AssetStatus
from core import audit
from core.context import get_current_tenant_id
from core.exceptions import BusinessRuleError
from core.services import BaseService

from .models import DiscrepancyType, Inventory, InventoryItem, InventoryStatus


class InventoryService(BaseService):
    @transaction.atomic
    def open_inventory(self, *, title: str, responsible_id: UUID | str) -> Inventory:
        tenant_id = get_current_tenant_id()
        if tenant_id is None:
            raise BusinessRuleError("Sem tenant no contexto.", code="no_tenant")
        mes = timezone.localdate().replace(day=1)
        inventory = Inventory.objects.create(
            tenant_id=tenant_id,
            title=title,
            reference_month=mes,
            responsible_id=responsible_id,
            status=InventoryStatus.OPEN,
        )
        # Gera a lista esperada: todos os bens ativos (não baixados).
        assets = Asset.objects.for_current_tenant().alive().exclude(status=AssetStatus.WRITTEN_OFF)
        InventoryItem.objects.bulk_create(
            [
                InventoryItem(
                    tenant_id=tenant_id,
                    inventory=inventory,
                    asset=asset,
                    expected_location_id=asset.location_id,
                )
                for asset in assets
            ]
        )
        audit.record(
            action="inventory.opened",
            entity_type="Inventory",
            entity_id=inventory.id,
            actor_id=responsible_id,
            diff={"title": title, "items": assets.count()},
        )
        return inventory

    @transaction.atomic
    def scan_item(
        self,
        *,
        item_id: UUID | str,
        found_location_id: UUID | str | None,
        condition_found: str,
        scanned_by_id: UUID | str,
    ) -> InventoryItem:
        item = (
            InventoryItem.objects.for_current_tenant()
            .alive()
            .select_related("inventory")
            .get(pk=item_id)
        )
        if item.inventory.status != InventoryStatus.OPEN:
            raise BusinessRuleError("Inventário já está fechado.", code="inventory_closed")
        item.found = True
        item.found_location_id = found_location_id or item.expected_location_id
        item.condition_found = condition_found
        item.scanned_at = timezone.now()
        item.scanned_by_id = scanned_by_id
        item.save(
            update_fields=[
                "found",
                "found_location",
                "condition_found",
                "scanned_at",
                "scanned_by",
                "updated_at",
            ]
        )
        return item

    @transaction.atomic
    def close_inventory(self, *, inventory_id: UUID | str, actor_id: UUID | str) -> Inventory:
        inventory = Inventory.objects.for_current_tenant().alive().get(pk=inventory_id)
        if inventory.status == InventoryStatus.CLOSED:
            raise BusinessRuleError("Inventário já está fechado.", code="already_closed")
        inventory.status = InventoryStatus.CLOSED
        inventory.closed_at = timezone.now()
        inventory.save(update_fields=["status", "closed_at", "updated_at"])
        audit.record(
            action="inventory.closed",
            entity_type="Inventory",
            entity_id=inventory.id,
            actor_id=actor_id,
        )
        return inventory

    @transaction.atomic
    def rename_inventory(self, *, inventory_id: UUID | str, title: str, actor_id: UUID | str) -> Inventory:
        inventory = Inventory.objects.for_current_tenant().alive().get(pk=inventory_id)
        if inventory.title == title:
            return inventory
        inventory.title = title
        inventory.save(update_fields=["title", "updated_at"])
        audit.record(
            action="inventory.updated",
            entity_type="Inventory",
            entity_id=inventory.id,
            actor_id=actor_id,
            diff={"title": title},
        )
        return inventory

    @transaction.atomic
    def delete_inventory(self, *, inventory_id: UUID | str, actor_id: UUID | str) -> None:
        """Descarta a conferência inteira (soft delete) — os bens não são tocados."""
        inventory = Inventory.objects.for_current_tenant().alive().get(pk=inventory_id)
        agora = timezone.now()
        InventoryItem.objects.filter(inventory=inventory, deleted_at__isnull=True).update(
            deleted_at=agora
        )
        inventory.deleted_at = agora
        inventory.save(update_fields=["deleted_at", "updated_at"])
        audit.record(
            action="inventory.deleted",
            entity_type="Inventory",
            entity_id=inventory.id,
            actor_id=actor_id,
            diff={"title": inventory.title},
        )

    def report(self, *, inventory_id: UUID | str) -> dict[str, int]:
        items = InventoryItem.objects.for_current_tenant().alive().filter(inventory_id=inventory_id)
        total = items.count()
        found = items.filter(found=True).count()
        wrong_location = sum(
            1 for i in items if i.discrepancy == DiscrepancyType.WRONG_LOCATION
        )
        return {
            "total": total,
            "found": found,
            "not_found": total - found,
            "wrong_location": wrong_location,
        }
