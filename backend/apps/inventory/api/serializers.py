from __future__ import annotations

from rest_framework import serializers

from apps.assets.models import AssetCondition

from ..models import Inventory, InventoryItem


class InventorySerializer(serializers.ModelSerializer):
    responsible_name = serializers.CharField(source="responsible.display_name", read_only=True)

    class Meta:
        model = Inventory
        fields = ["id", "title", "status", "responsible_name", "created_at", "closed_at"]
        read_only_fields = fields


class InventoryItemSerializer(serializers.ModelSerializer):
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    expected_location_name = serializers.CharField(
        source="expected_location.name", read_only=True, default=None
    )
    found_location_name = serializers.CharField(
        source="found_location.name", read_only=True, default=None
    )
    discrepancy = serializers.CharField(read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            "id",
            "asset",
            "asset_tag",
            "asset_name",
            "expected_location_name",
            "found",
            "found_location",
            "found_location_name",
            "condition_found",
            "discrepancy",
            "scanned_at",
        ]
        read_only_fields = fields


class OpenInventorySerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)


class ScanSerializer(serializers.Serializer):
    item = serializers.UUIDField()
    found_location = serializers.UUIDField(required=False, allow_null=True)
    condition_found = serializers.ChoiceField(
        choices=AssetCondition.choices, required=False, allow_blank=True, default=""
    )
