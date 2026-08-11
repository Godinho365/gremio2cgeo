from __future__ import annotations

from rest_framework import serializers

from ..models import CreditEntry, Payment


class PaymentSerializer(serializers.ModelSerializer):
    """O que a tela precisa para mostrar o QR e saber se já caiu."""

    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "method",
            "amount",
            "status",
            "status_label",
            "qr_code",
            "qr_code_base64",
            "ticket_url",
            "expires_at",
            "paid_at",
        ]
        read_only_fields = fields


class CreditEntrySerializer(serializers.ModelSerializer):
    reason_label = serializers.CharField(source="get_reason_display", read_only=True)

    class Meta:
        model = CreditEntry
        fields = ["id", "amount", "reason", "reason_label", "note", "created_at"]
        read_only_fields = fields


class CreditBalanceSerializer(serializers.Serializer):
    balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    entries = CreditEntrySerializer(many=True)
