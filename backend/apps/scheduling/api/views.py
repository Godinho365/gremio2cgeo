"""Agenda HTTP layer. Reservas passam pelo BookingService; disponibilidade é CRUD."""
from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import RoleCode
from core.exceptions import BusinessRuleError
from core.permissions import HasAnyRole
from core.viewsets import TenantCrudViewSet, TenantScopedViewSet

from ..models import Booking
from ..services import BookingService
from .serializers import AvailabilitySerializer, BookingCreateSerializer, BookingSerializer

_MANAGE_ROLES = (RoleCode.ADMIN, RoleCode.DIRECTOR)


def _is_manager(user) -> bool:
    return user.is_superuser or user.roles.filter(code__in=_MANAGE_ROLES).exists()


class AvailabilityViewSet(TenantCrudViewSet):
    serializer_class = AvailabilitySerializer
    required_roles = _MANAGE_ROLES

    def get_permissions(self):  # type: ignore[override]
        # read = qualquer autenticado (para ver o calendário); escrita = admin/diretor.
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), HasAnyRole()]

    def get_queryset(self):  # type: ignore[override]
        qs = super().get_queryset()
        asset = self.request.query_params.get("asset")
        return qs.filter(asset_id=asset) if asset else qs


class BookingViewSet(TenantScopedViewSet):
    serializer_class = BookingSerializer
    queryset = Booking.objects.none()
    service = BookingService()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):  # type: ignore[override]
        qs = self.service.repository.all().select_related("asset", "requester")
        asset = self.request.query_params.get("asset")
        status_f = self.request.query_params.get("status")
        if asset:
            qs = qs.filter(asset_id=asset)
        if status_f:
            qs = qs.filter(status=status_f)
        # Só reservas que ainda não terminaram (filas de aprovação/cautela).
        if self.request.query_params.get("upcoming") in ("1", "true"):
            qs = qs.filter(end_at__gte=timezone.now())
        return qs.order_by("start_at")  # ordem estável (paginação previsível)

    @extend_schema(request=BookingCreateSerializer, responses={201: BookingSerializer})
    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        payload = BookingCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        # Admin/Diretor reserva em nome de outro usuário; os demais, só para si.
        requester = payload.validated_data.get("requester")
        if requester and requester.pk != request.user.pk and not _is_manager(request.user):
            raise BusinessRuleError(
                "Apenas Admin/Diretor reservam em nome de outro usuário.", code="forbidden"
            )
        booking = self.service.create_booking(
            asset_id=payload.validated_data["asset"].id,
            requester_id=str(requester.pk if requester else request.user.pk),
            start_at=payload.validated_data["start_at"],
            end_at=payload.validated_data["end_at"],
            notes=payload.validated_data.get("notes", ""),
        )
        return Response(BookingSerializer(booking).data, status=201)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Exclui a reserva do histórico (soft delete). Só gestor."""
        if not _is_manager(request.user):
            raise BusinessRuleError("Apenas Admin/Diretor excluem reservas.", code="forbidden")
        self.service.repository.soft_delete(self.get_object())
        return Response(status=204)

    @extend_schema(responses={200: BookingSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: str = "") -> Response:
        if not _is_manager(request.user):
            raise BusinessRuleError("Apenas Admin/Diretor aprovam reservas.", code="forbidden")
        booking = self.service.approve_booking(booking_id=pk, approver_id=str(request.user.pk))
        return Response(BookingSerializer(booking).data)

    @extend_schema(responses={200: BookingSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str = "") -> Response:
        booking = self.service.repository.get(pk)
        # requester cancela a própria; admin/director cancela qualquer uma.
        if booking.requester_id != request.user.pk and not _is_manager(request.user):
            raise BusinessRuleError("Sem permissão para cancelar esta reserva.", code="forbidden")
        booking = self.service.cancel_booking(booking_id=pk, actor_id=str(request.user.pk))
        return Response(BookingSerializer(booking).data)
