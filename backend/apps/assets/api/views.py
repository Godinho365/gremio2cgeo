"""Patrimônio HTTP layer. Asset creation goes through AssetService (has rules);
catalog entities use the generic tenant-scoped CRUD. No business logic here.
"""
from __future__ import annotations

import io

import qrcode
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.custody.models import OPEN_CUSTODY_STATUSES, Custody
from apps.scheduling.models import Booking, BookingStatus
from core.exceptions import BusinessRuleError
from core.permissions import ExcludesRoles, HasAnyRole
from core.viewsets import TenantCrudViewSet, TenantScopedViewSet

from ...accounts.models import RoleCode
from ..models import Asset, AssetStatus
from ..services import AssetService
from .serializers import (
    AcquisitionSerializer,
    AssetCreateSerializer,
    AssetSerializer,
    AssetUpdateSerializer,
    CategorySerializer,
    LocationSerializer,
    SupplierSerializer,
)

# Who can manage the catalog / patrimônio (docs/produto/personas-perfis.md).
_MANAGE_ROLES = (RoleCode.ADMIN, RoleCode.DIRECTOR)


class InUseGuardMixin:
    """Registro em uso por algum bem não é excluído — o bem ficaria sem referência."""

    rotulo = "registro"

    def get_queryset(self):  # type: ignore[override]
        return super().get_queryset().annotate(  # type: ignore[misc]
            asset_count=Count("assets", filter=Q(assets__deleted_at__isnull=True))
        )

    def perform_destroy(self, instance: object) -> None:
        em_uso = instance.assets.filter(deleted_at__isnull=True).count()  # type: ignore[attr-defined]
        if em_uso:
            raise BusinessRuleError(
                f"{em_uso} {'bem usa' if em_uso == 1 else 'bens usam'} este {self.rotulo}. "
                "Troque esses bens antes de excluir.",
                code="in_use",
            )
        super().perform_destroy(instance)  # type: ignore[misc]


class CategoryViewSet(InUseGuardMixin, TenantCrudViewSet):
    """Leitura: qualquer usuário (filtro do catálogo); escrita: gestor."""

    serializer_class = CategorySerializer
    required_roles = _MANAGE_ROLES
    rotulo = "tipo"

    def get_permissions(self):  # type: ignore[override]
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated(), HasAnyRole()]
        return [IsAuthenticated()]


class LocationViewSet(InUseGuardMixin, TenantCrudViewSet):
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = _MANAGE_ROLES
    rotulo = "local"


class SupplierViewSet(TenantCrudViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = _MANAGE_ROLES


class AcquisitionViewSet(TenantCrudViewSet):
    serializer_class = AcquisitionSerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = _MANAGE_ROLES




class AssetViewSet(TenantScopedViewSet):
    serializer_class = AssetSerializer
    queryset = Asset.objects.none()  # schema introspection; runtime uses get_queryset
    service = AssetService()
    permission_classes = [IsAuthenticated]
    excluded_roles = (RoleCode.BARBERSHOP_CLIENT,)

    def get_permissions(self):  # type: ignore[override]
        # read = any authenticated user except Cliente da Barbearia; write = admin/director.
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated(), HasAnyRole()]
        return [IsAuthenticated(), ExcludesRoles()]

    required_roles = _MANAGE_ROLES

    def get_queryset(self):  # type: ignore[override]
        # Situação real do bem para o catálogo, sem precisar buscar cautelas/reservas.
        open_custody = Custody.objects.filter(
            asset_id=OuterRef("pk"),
            status__in=OPEN_CUSTODY_STATUSES,
            deleted_at__isnull=True,
        )
        now = timezone.now()
        approved = Booking.objects.filter(
            asset_id=OuterRef("pk"), status=BookingStatus.APPROVED, deleted_at__isnull=True
        )
        # Reserva já em curso = bem está com a pessoa; reserva futura = apenas reservado.
        booked_now = approved.filter(start_at__lte=now, end_at__gt=now)
        booked_later = approved.filter(start_at__gt=now)
        qs = (
            self.service.repository.all()
            .select_related("category", "location")
            .annotate(
                has_open_custody=Exists(open_custody),
                is_reserved_now=Exists(booked_now),
                has_upcoming_booking=Exists(booked_later),
            )
            .order_by("-created_at")
        )
        params = self.request.query_params
        # Filtros do catálogo/patrimônio: tipo (categoria), local, situação e busca.
        category = params.get("category")
        if category:
            qs = qs.filter(category_id=category)
        location = params.get("location")
        if location:
            qs = qs.filter(location_id=location)
        status_f = params.get("status")
        if status_f:
            qs = qs.filter(status=status_f)
        search = (params.get("q") or "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(asset_tag__icontains=search))
        if params.get("bookable") in ("1", "true"):
            qs = qs.filter(is_bookable=True)
        return qs

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"])
    def stats(self, request: Request) -> Response:
        """Quantitativo de bens por situação (todos do tenant, sem filtros)."""
        rows = self.service.repository.all().values("status").annotate(n=Count("id"))
        counts = {r["status"]: r["n"] for r in rows}
        data = {s.value: counts.get(s.value, 0) for s in AssetStatus}
        data["total"] = sum(data.values())
        return Response(data)

    @extend_schema(request=AssetCreateSerializer, responses={201: AssetSerializer})
    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        payload = AssetCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        asset_tag = data.pop("asset_tag", None) or None
        asset = self.service.create_asset(
            asset_tag=asset_tag,
            actor_id=getattr(request.user, "id", None),
            **data,
        )
        return Response(AssetSerializer(asset).data, status=201)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Tira o bem do acervo. Só gestor (ver get_permissions)."""
        self.service.delete_asset(
            asset=self.get_object(), actor_id=getattr(request.user, "id", None)
        )
        return Response(status=204)

    @extend_schema(request=AssetUpdateSerializer, responses={200: AssetSerializer})
    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        partial = bool(kwargs.get("partial", False))
        instance = self.get_object()
        serializer = AssetUpdateSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AssetSerializer(instance).data)

    def partial_update(self, request: Request, *args: object, **kwargs: object) -> Response:
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @extend_schema(responses={200: OpenApiResponse(description="PNG do QR Code")})
    @action(detail=True, methods=["get"], url_path="qrcode")
    def qrcode_png(self, request: Request, pk: str | None = None) -> HttpResponse:
        """QR Code da etiqueta patrimonial (Art.30 a)."""
        asset = self.get_object()
        img = qrcode.make(asset.asset_tag)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return HttpResponse(buffer.getvalue(), content_type="image/png")
