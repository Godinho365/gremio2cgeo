"""Inventário periódico (Art.30 b): conferir se os bens continuam nos locais.

Ver docs/modulos/inventario.md. A divergência é derivada dos campos do item.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.assets.models import Asset, AssetCondition, Location
from core.models import TenantScopedModel


class InventoryStatus(models.TextChoices):
    OPEN = "open", "Em andamento"
    CLOSED = "closed", "Fechado"


class Inventory(TenantScopedModel):
    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=InventoryStatus.choices, default=InventoryStatus.OPEN
    )
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="inventories"
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "inventory"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class DiscrepancyType(models.TextChoices):
    NONE = "none", "Sem divergência"
    NOT_FOUND = "not_found", "Não encontrado"
    WRONG_LOCATION = "wrong_location", "Local divergente"


class InventoryItem(TenantScopedModel):
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name="items")
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="inventory_items")
    expected_location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    found = models.BooleanField(default=False)
    found_location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    condition_found = models.CharField(
        max_length=20, choices=AssetCondition.choices, blank=True
    )
    scanned_at = models.DateTimeField(null=True, blank=True)
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        db_table = "inventory_item"
        constraints = [
            models.UniqueConstraint(
                fields=["inventory", "asset"], name="uq_inventory_item_asset"
            )
        ]

    @property
    def discrepancy(self) -> str:
        if not self.found:
            return DiscrepancyType.NOT_FOUND
        if self.found_location_id and self.found_location_id != self.expected_location_id:
            return DiscrepancyType.WRONG_LOCATION
        return DiscrepancyType.NONE

    def __str__(self) -> str:
        return f"{self.inventory_id} · {self.asset_id}"
