from __future__ import annotations

from rest_framework import serializers

from ..models import Asset


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = [
            "id",
            "asset_tag",
            "name",
            "description",
            "status",
            "condition",
            "acquisition_value",
            "protection_notes",
            "is_bookable",
            "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]


class AssetCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = [
            "asset_tag",
            "name",
            "description",
            "condition",
            "acquisition_value",
            "protection_notes",
            "is_bookable",
        ]
