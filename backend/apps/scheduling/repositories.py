from __future__ import annotations

from datetime import datetime
from uuid import UUID

from django.db import models

from core.repositories import BaseRepository

from .models import ACTIVE_BOOKING_STATUSES, Booking


class BookingRepository(BaseRepository[Booking]):
    model = Booking

    def overlapping(
        self,
        *,
        asset_id: UUID | str,
        start_at: datetime,
        end_at: datetime,
        exclude_id: UUID | str | None = None,
    ) -> models.QuerySet[Booking]:
        """Active bookings for the asset whose interval overlaps [start_at, end_at) (RN-B1)."""
        qs = self.query().filter(
            asset_id=asset_id,
            status__in=ACTIVE_BOOKING_STATUSES,
            start_at__lt=end_at,
            end_at__gt=start_at,
        )
        if exclude_id is not None:
            qs = qs.exclude(id=exclude_id)
        return qs
