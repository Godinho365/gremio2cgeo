"""BookingService — regras da reserva (RN-B1..B3). Ver docs/modulos/reservas.md."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import RoleCode, User
from apps.assets.models import Asset, AssetStatus
from apps.finance.models import FinancialStatus, PlanCode
from apps.finance.repositories import FinanceRepository
from core import audit
from core.exceptions import BusinessRuleError, ConflictError
from core.services import BaseService

from .models import Booking, BookingStatus
from .repositories import BookingRepository

_UNBOOKABLE_STATUSES = (AssetStatus.MAINTENANCE, AssetStatus.WRITTEN_OFF)

# Fora da gestão, só reserva quem tem Associado Full ativo e em dia — a
# Assinatura Barbearia não dá acesso ao patrimônio, e vencido/inadimplente
# perde o direito até regularizar (mesma régua da Barbearia).
_STAFF_ROLES = (RoleCode.ADMIN, RoleCode.DIRECTOR, RoleCode.INVENTORY, RoleCode.AUDITOR)
_RESERVATION_BLOCKING_STATUSES = (FinancialStatus.OVERDUE, FinancialStatus.DELINQUENT)


class BookingService(BaseService):
    def __init__(
        self,
        repository: BookingRepository | None = None,
        finance_profiles: FinanceRepository | None = None,
    ) -> None:
        self.repository = repository or BookingRepository()
        self.finance_profiles = finance_profiles or FinanceRepository()

    def _assert_can_reserve(self, requester_id: UUID | str) -> None:
        requester = User.objects.get(pk=requester_id)
        if requester.is_superuser or requester.roles.filter(code__in=_STAFF_ROLES).exists():
            return
        profile = self.finance_profiles.profile_for_user(requester_id)
        elegivel = (
            profile is not None
            and profile.is_active
            and profile.plan == PlanCode.ASSOCIADO
            and profile.financial_status not in _RESERVATION_BLOCKING_STATUSES
        )
        if not elegivel:
            raise BusinessRuleError(
                "Só quem tem Associado Full ativo e em dia pode reservar bens do patrimônio.",
                code="associado_full_required",
            )

    def _assert_no_overlap(
        self,
        asset_id: UUID | str,
        start_at: datetime,
        end_at: datetime,
        exclude_id: UUID | str | None = None,
    ) -> None:
        if self.repository.overlapping(
            asset_id=asset_id, start_at=start_at, end_at=end_at, exclude_id=exclude_id
        ).exists():
            raise ConflictError(
                "Já existe uma reserva nesse período para o bem.", code="booking_overlap"
            )

    @transaction.atomic
    def create_booking(
        self,
        *,
        asset_id: UUID | str,
        requester_id: UUID | str,
        start_at: datetime,
        end_at: datetime,
        notes: str = "",
    ) -> Booking:
        self._assert_can_reserve(requester_id)
        if start_at >= end_at:
            raise BusinessRuleError("Início deve ser anterior ao término.", code="invalid_interval")

        # Não permite reservar em datas passadas (comparação por dia; reservas são all-day).
        if timezone.localtime(start_at).date() < timezone.localdate():
            raise BusinessRuleError(
                "Não é possível reservar em datas passadas.", code="start_in_past"
            )

        # RN-B3: bem precisa ser reservável e não estar em manutenção/baixado.
        asset = Asset.objects.for_current_tenant().alive().get(pk=asset_id)
        if not asset.is_bookable or asset.status in _UNBOOKABLE_STATUSES:
            raise BusinessRuleError(
                "Este bem não está disponível para reserva.", code="not_bookable"
            )

        self._assert_no_overlap(asset_id, start_at, end_at)  # RN-B1

        booking = self.repository.create(
            asset_id=asset_id,
            requester_id=requester_id,
            start_at=start_at,
            end_at=end_at,
            notes=notes,
            status=BookingStatus.PENDING,
        )
        audit.record(
            action="booking.created",
            entity_type="Booking",
            entity_id=booking.id,
            actor_id=requester_id,
        )
        return booking

    @transaction.atomic
    def approve_booking(self, *, booking_id: UUID | str, approver_id: UUID | str) -> Booking:
        booking = self.repository.get(booking_id)
        if booking.status != BookingStatus.PENDING:
            raise BusinessRuleError(
                "Só reservas pendentes podem ser aprovadas.", code="not_pending"
            )
        # Re-check overlap against other active bookings (RN-B1).
        self._assert_no_overlap(
            booking.asset_id, booking.start_at, booking.end_at, exclude_id=booking.id
        )
        booking.status = BookingStatus.APPROVED
        booking.approver_id = approver_id
        booking.save(update_fields=["status", "approver", "updated_at"])
        audit.record(
            action="booking.approved",
            entity_type="Booking",
            entity_id=booking.id,
            actor_id=approver_id,
        )
        return booking

    @transaction.atomic
    def cancel_booking(self, *, booking_id: UUID | str, actor_id: UUID | str) -> Booking:
        booking = self.repository.get(booking_id)
        if booking.status in (BookingStatus.CANCELLED, BookingStatus.COMPLETED):
            raise BusinessRuleError("Reserva não pode ser cancelada.", code="not_cancellable")
        booking.status = BookingStatus.CANCELLED
        booking.save(update_fields=["status", "updated_at"])
        audit.record(
            action="booking.cancelled",
            entity_type="Booking",
            entity_id=booking.id,
            actor_id=actor_id,
        )
        return booking
