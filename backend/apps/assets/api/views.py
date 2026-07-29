"""Patrimônio HTTP layer. Asset creation goes through AssetService (has rules);
catalog entities use the generic tenant-scoped CRUD. No business logic here.
"""
from __future__ import annotations

import io

import qrcode
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from core.permissions import HasAnyRole
from core.viewsets import TenantCrudViewSet, TenantScopedViewSet

from ...accounts.models import RoleCode
from ..models import Asset
from ..services import AssetService
from .serializers import (
    AcquisitionSerializer,
    AssetCreateSerializer,
    AssetSerializer,
    CategorySerializer,
    LocationSerializer,
    SupplierSerializer,
)

# Who can manage the catalog / patrimônio (docs/produto/personas-perfis.md).
_MANAGE_ROLES = (RoleCode.ADMIN, RoleCode.DIRECTOR)


class CategoryViewSet(TenantCrudViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = _MANAGE_ROLES


class LocationViewSet(TenantCrudViewSet):
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = _MANAGE_ROLES


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

    def get_permissions(self):  # type: ignore[override]
        # read = any authenticated user; write = admin/director.
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated(), HasAnyRole()]
        return [IsAuthenticated()]

    required_roles = _MANAGE_ROLES

    def get_queryset(self):  # type: ignore[override]
        return (
            self.service.repository.all()
            .select_related("category", "location")
            .order_by("-created_at")
        )

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

    @extend_schema(responses={200: OpenApiResponse(description="PNG do QR Code")})
    @action(detail=True, methods=["get"], url_path="qrcode")
    def qrcode_png(self, request: Request, pk: str | None = None) -> HttpResponse:
        """QR Code da etiqueta patrimonial (Art.30 a)."""
        asset = self.get_object()
        img = qrcode.make(asset.asset_tag)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return HttpResponse(buffer.getvalue(), content_type="image/png")
