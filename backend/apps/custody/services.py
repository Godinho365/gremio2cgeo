"""CustodyService — regras da cautela (Art.30 d, RN-C1..C6). Ver docs/modulos/cautelas.md."""
from __future__ import annotations

import hashlib
from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.assets.models import Asset, AssetStatus
from apps.scheduling.models import Booking, BookingStatus
from core import audit
from core.context import get_current_tenant_id
from core.exceptions import BusinessRuleError
from core.services import BaseService

from .models import (
    OPEN_CUSTODY_STATUSES,
    Custody,
    CustodyStatus,
    Inspection,
    InspectionOutcome,
    Return,
)
from .repositories import CustodyRepository

# Asset states from which a custody may be issued.
_ISSUABLE_ASSET_STATUSES = (AssetStatus.AVAILABLE, AssetStatus.RESERVED)


class CustodyService(BaseService):
    def __init__(self, repository: CustodyRepository | None = None) -> None:
        self.repository = repository or CustodyRepository()

    @transaction.atomic
    def issue_custody(
        self,
        *,
        asset_id: UUID | str,
        holder_id: UUID | str,
        issued_by_id: UUID | str,
        due_at: datetime,
        condition_out: str,
        holder_signature: bool,
        issuer_signature: bool,
        booking_id: UUID | str | None = None,
        notes: str = "",
    ) -> Custody:
        # RN-C1: cautela ativa exige as duas assinaturas.
        if not (holder_signature and issuer_signature):
            raise BusinessRuleError(
                "A cautela exige a assinatura do associado e do diretor.",
                code="missing_signature",
            )

        asset = Asset.objects.for_current_tenant().alive().select_for_update().get(pk=asset_id)
        if asset.status not in _ISSUABLE_ASSET_STATUSES:
            raise BusinessRuleError(
                "Bem não está disponível para cautela.", code="asset_not_issuable"
            )
        # RN-C2: no máximo uma cautela aberta por bem.
        if self.repository.has_open_for_asset(asset_id):
            raise BusinessRuleError(
                "Já existe uma cautela ativa para este bem.", code="custody_open"
            )

        now = timezone.now()
        custody = self.repository.create(
            asset_id=asset_id,
            booking_id=booking_id,
            holder_id=holder_id,
            issued_by_id=issued_by_id,
            due_at=due_at,
            condition_out=condition_out,  # RN-C3
            status=CustodyStatus.ACTIVE,
            holder_signed_at=now,
            issuer_signed_at=now,
            notes=notes,
        )
        custody.term_hash = self._term_hash(custody)
        custody.save(update_fields=["term_hash", "updated_at"])

        asset.status = AssetStatus.IN_USE
        asset.save(update_fields=["status", "updated_at"])

        if booking_id:
            Booking.objects.filter(pk=booking_id).update(status=BookingStatus.COMPLETED)

        audit.record(
            action="custody.issued",
            entity_type="Custody",
            entity_id=custody.id,
            actor_id=issued_by_id,
            diff={"asset": asset.asset_tag, "holder": str(holder_id)},
        )
        return custody

    @transaction.atomic
    def return_custody(
        self,
        *,
        custody_id: UUID | str,
        received_by_id: UUID | str,
        condition_in: str,
        outcome: str,
        notes: str = "",
    ) -> Custody:
        custody = self.repository.get(custody_id)
        if custody.status not in OPEN_CUSTODY_STATUSES:
            raise BusinessRuleError("Esta cautela não está em aberto.", code="custody_not_open")

        ret = Return.objects.create(
            tenant_id=get_current_tenant_id(),
            custody=custody,
            received_by_id=received_by_id,
        )
        Inspection.objects.create(
            tenant_id=get_current_tenant_id(),
            ret=ret,
            condition_in=condition_in,  # RN-C3
            outcome=outcome,
        )

        asset = custody.asset
        # RN-C5: encaminhamento conforme resultado da inspeção.
        if outcome == InspectionOutcome.MISSING:
            custody.status = CustodyStatus.LOST
        else:
            custody.status = CustodyStatus.RETURNED
            asset.status = (
                AssetStatus.MAINTENANCE
                if outcome == InspectionOutcome.DAMAGE
                else AssetStatus.AVAILABLE
            )
            asset.save(update_fields=["status", "updated_at"])
        custody.notes = (custody.notes + "\n" + notes).strip() if notes else custody.notes
        custody.save(update_fields=["status", "notes", "updated_at"])

        audit.record(
            action="custody.returned",
            entity_type="Custody",
            entity_id=custody.id,
            actor_id=received_by_id,
            diff={"outcome": outcome, "condition_in": condition_in},
        )
        return custody

    @staticmethod
    def _term_hash(custody: Custody) -> str:
        payload = f"{custody.pk}|{custody.asset.pk}|{custody.holder.pk}|{custody.issued_at}"
        return hashlib.sha256(payload.encode()).hexdigest()


def mark_overdue_custodies() -> int:
    """RN-C4: cautelas ativas com prazo vencido viram 'atrasada'. Chamado por Celery."""
    now = timezone.now()
    return Custody.objects.filter(status=CustodyStatus.ACTIVE, due_at__lt=now).update(
        status=CustodyStatus.OVERDUE
    )
