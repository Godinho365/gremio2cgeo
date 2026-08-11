from __future__ import annotations

from rest_framework import serializers

from apps.accounts.models import User
from apps.assets.api.serializers import TenantRelationsMixin
from apps.assets.models import Asset
from core.context import get_current_tenant_id

from ..models import Availability, Booking


class AvailabilitySerializer(TenantRelationsMixin, serializers.ModelSerializer):
    tenant_scoped_fields = {"asset": Asset}

    class Meta:
        model = Availability
        fields = ["id", "asset", "weekday", "start_time", "end_time", "slot_minutes", "created_at"]
        read_only_fields = ["id", "created_at"]


class BookingSerializer(serializers.ModelSerializer):
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    requester_name = serializers.CharField(source="requester.display_name", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "asset",
            "asset_tag",
            "asset_name",
            "requester",
            "requester_name",
            "start_at",
            "end_at",
            "status",
            "notes",
            "created_at",
        ]
        read_only_fields = fields


class BookingCreateSerializer(TenantRelationsMixin, serializers.ModelSerializer):
    """`requester` só é aceito de Admin/Diretor (reserva em nome de outro)."""

    tenant_scoped_fields = {"asset": Asset}
    requester = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.none(), required=False, allow_null=True
    )

    class Meta:
        model = Booking
        fields = ["asset", "requester", "start_at", "end_at", "notes"]

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        tenant_id = get_current_tenant_id()
        self.fields["requester"].queryset = (  # type: ignore[attr-defined]
            User.objects.filter(tenant_id=tenant_id) if tenant_id else User.objects.none()
        )
