"""HTTP layer: translates requests to AssetService calls. No business logic here."""
from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response

from core.viewsets import TenantScopedViewSet

from ..services import AssetService
from .serializers import AssetCreateSerializer, AssetSerializer


class AssetViewSet(TenantScopedViewSet):
    serializer_class = AssetSerializer
    service = AssetService()

    def get_queryset(self):  # type: ignore[override]
        return self.service.repository.all().order_by("-created_at")

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        payload = AssetCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        asset = self.service.create_asset(
            actor_id=getattr(request.user, "id", None), **payload.validated_data
        )
        return Response(AssetSerializer(asset).data, status=201)
