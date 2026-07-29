"""Asset (Bem). Reference model. Full field dictionary: docs/dominio/entidades.md.

Scaffold subset — category/location/acquisition FKs to be added in Sprint 2.
"""
from __future__ import annotations

from django.db import models

from core.models import TenantScopedModel


class AssetStatus(models.TextChoices):
    AVAILABLE = "available", "Disponível"
    RESERVED = "reserved", "Reservado"
    IN_USE = "in_use", "Em uso"
    MAINTENANCE = "maintenance", "Manutenção"
    WRITTEN_OFF = "written_off", "Baixado"


class AssetCondition(models.TextChoices):
    NEW = "new", "Novo"
    GOOD = "good", "Bom"
    REGULAR = "regular", "Regular"
    BAD = "bad", "Ruim"
    UNUSABLE = "unusable", "Inservível"


class Asset(TenantScopedModel):
    asset_tag = models.CharField(max_length=50)  # unique per tenant (RN-A1)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=AssetStatus.choices, default=AssetStatus.AVAILABLE
    )
    condition = models.CharField(
        max_length=20, choices=AssetCondition.choices, default=AssetCondition.GOOD
    )
    acquisition_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    protection_notes = models.TextField(blank=True)  # Art.30 c
    is_bookable = models.BooleanField(default=True)

    class Meta:
        db_table = "asset"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "asset_tag"], name="uq_asset_tag_per_tenant"
            )
        ]

    def __str__(self) -> str:
        return f"{self.asset_tag} — {self.name}"
