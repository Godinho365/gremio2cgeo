"""Patrimônio domain models. Field dictionary: docs/dominio/entidades.md.

Covers Art.30 a) (catalogar + etiquetas) and c) (protection_notes).
"""
from __future__ import annotations

from django.db import models

from core.models import TenantScopedModel


class Category(TenantScopedModel):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children"
    )

    class Meta:
        db_table = "category"
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name", "parent"], name="uq_category_name_per_parent"
            )
        ]

    def __str__(self) -> str:
        return self.name


class LocationType(models.TextChoices):
    UNIT = "unit", "Unidade"
    BUILDING = "building", "Prédio"
    FLOOR = "floor", "Andar"
    ROOM = "room", "Sala"


class Location(TenantScopedModel):
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=LocationType.choices, default=LocationType.ROOM)
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children"
    )

    class Meta:
        db_table = "location"

    def __str__(self) -> str:
        return self.name


class Supplier(TenantScopedModel):
    name = models.CharField(max_length=255)
    document = models.CharField(max_length=32, blank=True)  # CNPJ/CPF
    email = models.EmailField(blank=True)

    class Meta:
        db_table = "supplier"

    def __str__(self) -> str:
        return self.name


class AcquisitionType(models.TextChoices):
    PURCHASE = "purchase", "Compra"
    DONATION = "donation", "Doação"


class Acquisition(TenantScopedModel):
    type = models.CharField(max_length=20, choices=AcquisitionType.choices)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, null=True, blank=True, related_name="acquisitions"
    )
    document_ref = models.CharField(max_length=100, blank=True)  # NF / termo de doação
    date = models.DateField()
    value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "acquisition"

    def __str__(self) -> str:
        return f"{self.get_type_display()} {self.document_ref}".strip()


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
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, null=True, blank=True, related_name="assets"
    )
    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, null=True, blank=True, related_name="assets"
    )
    acquisition = models.ForeignKey(
        Acquisition, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets"
    )
    status = models.CharField(
        max_length=20, choices=AssetStatus.choices, default=AssetStatus.AVAILABLE
    )
    condition = models.CharField(
        max_length=20, choices=AssetCondition.choices, default=AssetCondition.GOOD
    )
    acquisition_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    protection_notes = models.TextField(blank=True)  # Art.30 c
    is_bookable = models.BooleanField(default=True)
    # Posição do bem na planta da sala (0..1 relativo à imagem). Null = não posicionado.
    plan_x = models.FloatField(null=True, blank=True)
    plan_y = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "asset"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "asset_tag"], name="uq_asset_tag_per_tenant"
            )
        ]

    def __str__(self) -> str:
        return f"{self.asset_tag} — {self.name}"


class FloorPlan(TenantScopedModel):
    """Planta (imagem) da sala/organização. Uma por tenant no MVP.

    Guarda a imagem como data URI (base64) para evitar dependência de storage/Pillow.
    """

    name = models.CharField(max_length=120, default="Planta")
    image_data = models.TextField()  # data:image/...;base64,...

    class Meta:
        db_table = "floor_plan"

    def __str__(self) -> str:
        return self.name
