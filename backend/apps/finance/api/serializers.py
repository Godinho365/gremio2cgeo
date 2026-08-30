from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.accounts.models import User
from apps.payments.models import PaymentMethod
from core.context import get_current_tenant_id

from ..models import AssociadoInvite, BillingProfile, Due, PlanCode


def _tenant_users_queryset():
    tenant_id = get_current_tenant_id()
    return User.objects.filter(tenant_id=tenant_id) if tenant_id else User.objects.none()


class BillingProfileSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.display_name", read_only=True)
    user_posto = serializers.CharField(source="user.posto_graduacao", read_only=True)
    plan_label = serializers.CharField(source="get_plan_display", read_only=True)
    financial_status_label = serializers.CharField(
        source="get_financial_status_display", read_only=True
    )

    class Meta:
        model = BillingProfile
        fields = [
            "id",
            "user",
            "user_name",
            "user_posto",
            "plan",
            "plan_label",
            "due_day",
            "started_period",
            "is_active",
            "financial_status",
            "financial_status_label",
            "last_payment_at",
        ]
        read_only_fields = ["id", "plan_label", "financial_status", "last_payment_at"]


class ActivateBillingSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.none())
    plan = serializers.ChoiceField(choices=PlanCode.choices)
    due_day = serializers.IntegerField(min_value=1, max_value=31)
    started_period = serializers.DateField()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = _tenant_users_queryset()  # type: ignore[attr-defined]


class UpdateDueDaySerializer(serializers.Serializer):
    due_day = serializers.IntegerField(min_value=1, max_value=31)


class AssociadoInviteSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.display_name", read_only=True)

    class Meta:
        model = AssociadoInvite
        fields = ["id", "user", "user_name", "token", "expires_at", "used_at", "created_at"]
        read_only_fields = fields


class GenerateInviteSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.none())

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = _tenant_users_queryset()  # type: ignore[attr-defined]


class DueSerializer(serializers.ModelSerializer):
    user = serializers.UUIDField(source="billing_profile.user_id", read_only=True)
    user_name = serializers.CharField(
        source="billing_profile.user.display_name", read_only=True
    )
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Due
        fields = [
            "id",
            "billing_profile",
            "user",
            "user_name",
            "period",
            "due_date",
            "amount",
            "status",
            "status_label",
            "paid_in_advance",
            "paid_at",
        ]
        read_only_fields = fields


class RegisterPaymentSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.none())
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    paid_at = serializers.DateTimeField()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = _tenant_users_queryset()  # type: ignore[attr-defined]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("O valor deve ser maior que zero.")
        return value
