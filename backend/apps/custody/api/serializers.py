from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCondition
from apps.scheduling.models import Booking
from core.context import get_current_tenant_id

from ..models import Custody, InspectionOutcome


class CustodySerializer(serializers.ModelSerializer):
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    holder_name = serializers.CharField(source="holder.username", read_only=True)
    issued_by_name = serializers.CharField(source="issued_by.username", read_only=True)

    class Meta:
        model = Custody
        fields = [
            "id",
            "asset",
            "asset_tag",
            "asset_name",
            "holder",
            "holder_name",
            "issued_by_name",
            "issued_at",
            "due_at",
            "condition_out",
            "status",
            "term_hash",
            "booking",
            "notes",
        ]
        read_only_fields = fields


class CustodyIssueSerializer(serializers.Serializer):
    asset = serializers.PrimaryKeyRelatedField(queryset=Asset.objects.none())
    holder = serializers.PrimaryKeyRelatedField(queryset=User.objects.none())
    booking = serializers.PrimaryKeyRelatedField(
        queryset=Booking.objects.none(), required=False, allow_null=True
    )
    due_at = serializers.DateTimeField()
    condition_out = serializers.ChoiceField(choices=AssetCondition.choices)
    holder_signature = serializers.BooleanField()
    issuer_signature = serializers.BooleanField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        tenant_id = get_current_tenant_id()
        users = User.objects.filter(tenant_id=tenant_id) if tenant_id else User.objects.none()
        self.fields["asset"].queryset = Asset.objects.for_current_tenant().alive()  # type: ignore[attr-defined]
        self.fields["holder"].queryset = users  # type: ignore[attr-defined]
        self.fields["booking"].queryset = Booking.objects.for_current_tenant().alive()  # type: ignore[attr-defined]


class CustodyReturnSerializer(serializers.Serializer):
    condition_in = serializers.ChoiceField(choices=AssetCondition.choices)
    outcome = serializers.ChoiceField(choices=InspectionOutcome.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
