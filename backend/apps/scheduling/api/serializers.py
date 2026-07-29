from __future__ import annotations

from rest_framework import serializers

from apps.assets.api.serializers import TenantRelationsMixin
from apps.assets.models import Asset

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
    requester_name = serializers.CharField(source="requester.username", read_only=True)

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
    tenant_scoped_fields = {"asset": Asset}

    class Meta:
        model = Booking
        fields = ["asset", "start_at", "end_at", "notes"]
