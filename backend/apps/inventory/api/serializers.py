from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from apps.assets.models import AssetCondition
from apps.custody.models import OPEN_CUSTODY_STATUSES, Custody
from apps.scheduling.models import Booking, BookingStatus

from ..models import Inventory, InventoryItem


class InventorySerializer(serializers.ModelSerializer):
    responsible_name = serializers.CharField(source="responsible.display_name", read_only=True)

    class Meta:
        model = Inventory
        fields = [
            "id",
            "title",
            "status",
            "reference_month",
            "responsible_name",
            "created_at",
            "closed_at",
        ]
        read_only_fields = fields


class InventoryUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)


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
    holder_name = serializers.SerializerMethodField()

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
            "holder_name",
            "scanned_at",
        ]
        read_only_fields = fields

    def get_holder_name(self, obj: InventoryItem) -> str | None:
        """Com quem o bem está hoje — vira o 'local encontrado' na conferência.

        Cautela em aberto tem prioridade; senão, reserva aprovada em curso.
        """
        cautela = (
            Custody.objects.filter(
                asset_id=obj.asset_id,
                status__in=OPEN_CUSTODY_STATUSES,
                deleted_at__isnull=True,
            )
            .select_related("holder")
            .first()
        )
        if cautela:
            return cautela.holder.display_name
        agora = timezone.now()
        reserva = (
            Booking.objects.filter(
                asset_id=obj.asset_id,
                status=BookingStatus.APPROVED,
                start_at__lte=agora,
                end_at__gt=agora,
                deleted_at__isnull=True,
            )
            .select_related("requester")
            .first()
        )
        return reserva.requester.display_name if reserva else None


class OpenInventorySerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)


class ScanSerializer(serializers.Serializer):
    item = serializers.UUIDField()
    found_location = serializers.UUIDField(required=False, allow_null=True)
    condition_found = serializers.ChoiceField(
        choices=AssetCondition.choices, required=False, allow_blank=True, default=""
    )
