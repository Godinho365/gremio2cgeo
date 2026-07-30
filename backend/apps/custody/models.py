"""Cautelas (Art.30 d): termo de responsabilidade assinado + inspeção na devolução.

Ver docs/modulos/cautelas.md e regras RN-C1..C6.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.assets.models import Asset, AssetCondition
from apps.scheduling.models import Booking
from core.models import TenantScopedModel


class CustodyStatus(models.TextChoices):
    ACTIVE = "active", "Ativa"
    RETURNED = "returned", "Devolvida"
    OVERDUE = "overdue", "Atrasada"
    LOST = "lost", "Extraviada"


# Statuses in which the asset is still out with the holder.
OPEN_CUSTODY_STATUSES = (CustodyStatus.ACTIVE, CustodyStatus.OVERDUE)


class Custody(TenantScopedModel):
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="custodies")
    booking = models.ForeignKey(
        Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name="custodies"
    )
    holder = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="held_custodies"
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="issued_custodies"
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    due_at = models.DateTimeField()
    condition_out = models.CharField(max_length=20, choices=AssetCondition.choices)
    status = models.CharField(
        max_length=20, choices=CustodyStatus.choices, default=CustodyStatus.ACTIVE
    )
    # Simple electronic signatures: audit trail = timestamp + term hash (RN-C1).
    holder_signed_at = models.DateTimeField(null=True, blank=True)
    issuer_signed_at = models.DateTimeField(null=True, blank=True)
    term_hash = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "custody"
        ordering = ["-issued_at"]
        indexes = [models.Index(fields=["asset", "status"])]

    def __str__(self) -> str:
        return f"Cautela {self.asset.asset_tag} → {self.holder}"


class InspectionOutcome(models.TextChoices):
    OK = "ok", "Sem dano"
    DAMAGE = "damage", "Com dano"
    MISSING = "missing", "Faltante"


class Return(TenantScopedModel):
    custody = models.OneToOneField(Custody, on_delete=models.CASCADE, related_name="return_record")
    returned_at = models.DateTimeField(auto_now_add=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="received_returns"
    )

    class Meta:
        db_table = "custody_return"

    def __str__(self) -> str:
        return f"Devolução {self.custody_id}"  # type: ignore[attr-defined]


class Inspection(TenantScopedModel):
    ret = models.OneToOneField(Return, on_delete=models.CASCADE, related_name="inspection")
    condition_in = models.CharField(max_length=20, choices=AssetCondition.choices)
    outcome = models.CharField(max_length=20, choices=InspectionOutcome.choices)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "custody_inspection"

    def __str__(self) -> str:
        return f"Inspeção {self.ret_id} ({self.outcome})"  # type: ignore[attr-defined]
