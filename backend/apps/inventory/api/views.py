"""Inventário HTTP layer (Art.30 b). Regras no InventoryService; sem lógica aqui."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import RoleCode
from core.exceptions import BusinessRuleError
from core.viewsets import TenantScopedViewSet

from ..models import Inventory, InventoryItem
from ..services import InventoryService
from .serializers import (
    InventoryItemSerializer,
    InventorySerializer,
    InventoryUpdateSerializer,
    OpenInventorySerializer,
    ScanSerializer,
)

_INVENTORY_ROLES = (RoleCode.ADMIN, RoleCode.DIRECTOR, RoleCode.INVENTORY)


def _can_inventory(user) -> bool:
    return user.is_superuser or user.roles.filter(code__in=_INVENTORY_ROLES).exists()


class InventoryViewSet(TenantScopedViewSet):
    serializer_class = InventorySerializer
    queryset = Inventory.objects.none()
    service = InventoryService()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):  # type: ignore[override]
        return Inventory.objects.for_current_tenant().alive().select_related("responsible")

    @extend_schema(request=OpenInventorySerializer, responses={201: InventorySerializer})
    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        if not _can_inventory(request.user):
            raise BusinessRuleError("Sem permissão para abrir inventário.", code="forbidden")
        payload = OpenInventorySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        inv = self.service.open_inventory(
            title=payload.validated_data["title"], responsible_id=str(request.user.pk)
        )
        return Response(InventorySerializer(inv).data, status=201)

    @extend_schema(request=InventoryUpdateSerializer, responses={200: InventorySerializer})
    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        if not _can_inventory(request.user):
            raise BusinessRuleError("Sem permissão para editar inventário.", code="forbidden")
        payload = InventoryUpdateSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        inv = self.service.rename_inventory(
            inventory_id=self.get_object().pk,
            title=payload.validated_data["title"],
            actor_id=str(request.user.pk),
        )
        return Response(InventorySerializer(inv).data)

    def partial_update(self, request: Request, *args: object, **kwargs: object) -> Response:
        return self.update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        if not _can_inventory(request.user):
            raise BusinessRuleError("Sem permissão para excluir inventário.", code="forbidden")
        self.service.delete_inventory(
            inventory_id=self.get_object().pk, actor_id=str(request.user.pk)
        )
        return Response(status=204)

    @extend_schema(responses={200: InventoryItemSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def items(self, request: Request, pk: str = "") -> Response:
        qs = (
            InventoryItem.objects.for_current_tenant()
            .alive()
            .filter(inventory_id=pk)
            .select_related("asset", "expected_location", "found_location")
            .order_by("asset__asset_tag")
        )
        return Response(InventoryItemSerializer(qs, many=True).data)

    @extend_schema(request=ScanSerializer, responses={200: InventoryItemSerializer})
    @action(detail=True, methods=["post"])
    def scan(self, request: Request, pk: str = "") -> Response:
        if not _can_inventory(request.user):
            raise BusinessRuleError("Sem permissão para conferir.", code="forbidden")
        payload = ScanSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        item = self.service.scan_item(
            item_id=str(payload.validated_data["item"]),
            found_location_id=payload.validated_data.get("found_location"),
            condition_found=payload.validated_data.get("condition_found", ""),
            scanned_by_id=str(request.user.pk),
        )
        return Response(InventoryItemSerializer(item).data)

    @extend_schema(responses={200: InventorySerializer})
    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk: str = "") -> Response:
        if not _can_inventory(request.user):
            raise BusinessRuleError("Sem permissão para fechar inventário.", code="forbidden")
        inv = self.service.close_inventory(inventory_id=pk, actor_id=str(request.user.pk))
        return Response(InventorySerializer(inv).data)

    @action(detail=True, methods=["get"])
    def report(self, request: Request, pk: str = "") -> Response:
        return Response(self.service.report(inventory_id=pk))
