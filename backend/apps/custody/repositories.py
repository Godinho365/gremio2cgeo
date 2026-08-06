from __future__ import annotations

from uuid import UUID

from core.repositories import BaseRepository

from .models import OPEN_CUSTODY_STATUSES, Custody, CustodyStatus


class CustodyRepository(BaseRepository[Custody]):
    model = Custody

    def has_open_for_asset(self, asset_id: UUID | str) -> bool:
        """RN-C2: at most one open custody per asset."""
        return self.query().filter(asset_id=asset_id, status__in=OPEN_CUSTODY_STATUSES).exists()

    def has_pending_or_open_for_asset(self, asset_id: UUID | str) -> bool:
        """Existe cautela solicitada (pendente) OU aberta — impede solicitar duas vezes."""
        statuses = (CustodyStatus.PENDING, *OPEN_CUSTODY_STATUSES)
        return self.query().filter(asset_id=asset_id, status__in=statuses).exists()
