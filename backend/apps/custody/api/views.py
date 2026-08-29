"""Cautelas HTTP layer (Art.30 d). Regras no CustodyService; sem lógica aqui."""
from __future__ import annotations

from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import RoleCode
from core.exceptions import BusinessRuleError
from core.permissions import ExcludesRoles
from core.viewsets import TenantScopedViewSet

from ..models import OPEN_CUSTODY_STATUSES, Custody, CustodyStatus
from ..services import CustodyService
from .serializers import CustodyIssueSerializer, CustodyReturnSerializer, CustodySerializer

_MANAGE_ROLES = (RoleCode.ADMIN, RoleCode.DIRECTOR)


def _is_manager(user) -> bool:
    return user.is_superuser or user.roles.filter(code__in=_MANAGE_ROLES).exists()


class CustodyViewSet(TenantScopedViewSet):
    serializer_class = CustodySerializer
    queryset = Custody.objects.none()
    service = CustodyService()
    permission_classes = [IsAuthenticated, ExcludesRoles]
    excluded_roles = (RoleCode.BARBERSHOP_CLIENT,)

    def get_queryset(self):  # type: ignore[override]
        qs = self.service.repository.all().select_related("asset", "holder", "issued_by")
        asset = self.request.query_params.get("asset")
        status_f = self.request.query_params.get("status")
        q = self.request.query_params.get("q")
        if asset:
            qs = qs.filter(asset_id=asset)
        if status_f == "open":
            # "Em aberto" = bem ainda com a pessoa (ativa ou atrasada).
            qs = qs.filter(status__in=OPEN_CUSTODY_STATUSES)
        elif status_f:
            qs = qs.filter(status=status_f)
        if q:
            qs = qs.filter(
                Q(asset__name__icontains=q)
                | Q(asset__asset_tag__icontains=q)
                | Q(holder__username__icontains=q)
                | Q(holder__nome_guerra__icontains=q)
                | Q(holder__posto_graduacao__icontains=q)
            )
        return qs.order_by("-issued_at")

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"])
    def stats(self, request: Request) -> Response:
        """Quantitativo de cautelas por situação (todas do tenant)."""
        rows = self.service.repository.all().values("status").annotate(n=Count("id"))
        counts = {r["status"]: r["n"] for r in rows}
        data = {s.value: counts.get(s.value, 0) for s in CustodyStatus}
        data["total"] = sum(data.values())
        data["open"] = data[CustodyStatus.ACTIVE] + data[CustodyStatus.OVERDUE]
        return Response(data)

    @extend_schema(request=CustodyIssueSerializer, responses={201: CustodySerializer})
    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Gestor entrega o bem (cautela já ativa); os demais apenas solicitam."""
        payload = CustodyIssueSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        booking = data.get("booking")
        common = {
            "asset_id": data["asset"].id,
            "holder_id": data["holder"].id,
            "issued_by_id": str(request.user.pk),
            "due_at": data["due_at"],
            "condition_out": data["condition_out"],
            "booking_id": booking.id if booking else None,
            "notes": data.get("notes", ""),
        }
        if _is_manager(request.user):
            custody = self.service.deliver_custody(issued_at=data.get("issued_at"), **common)
        else:
            custody = self.service.request_custody(**common)
        return Response(CustodySerializer(custody).data, status=201)

    @extend_schema(responses={200: CustodySerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: str = "") -> Response:
        if not _is_manager(request.user):
            raise BusinessRuleError("Apenas Admin/Diretor aprovam cautela.", code="forbidden")
        custody = self.service.approve_custody(custody_id=pk, approver_id=str(request.user.pk))
        return Response(CustodySerializer(custody).data)

    @extend_schema(responses={200: CustodySerializer})
    @action(detail=True, methods=["post"])
    def reject(self, request: Request, pk: str = "") -> Response:
        if not _is_manager(request.user):
            raise BusinessRuleError("Apenas Admin/Diretor rejeitam cautela.", code="forbidden")
        custody = self.service.reject_custody(custody_id=pk, actor_id=str(request.user.pk))
        return Response(CustodySerializer(custody).data)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        if not _is_manager(request.user):
            raise BusinessRuleError("Apenas Admin/Diretor excluem cautela.", code="forbidden")
        instance = self.get_object()
        self.service.repository.soft_delete(instance)
        return Response(status=204)

    @extend_schema(request=CustodyReturnSerializer, responses={200: CustodySerializer})
    @action(detail=True, methods=["post"], url_path="return")
    def return_(self, request: Request, pk: str = "") -> Response:
        if not _is_manager(request.user):
            raise BusinessRuleError("Apenas Admin/Diretor recebem devolução.", code="forbidden")
        payload = CustodyReturnSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        custody = self.service.return_custody(
            custody_id=pk,
            received_by_id=str(request.user.pk),
            condition_in=payload.validated_data["condition_in"],
            outcome=payload.validated_data["outcome"],
            notes=payload.validated_data.get("notes", ""),
        )
        return Response(CustodySerializer(custody).data)
