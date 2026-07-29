from __future__ import annotations

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from ..models import RoleCode, User


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "is_active", "roles", "date_joined"]
        read_only_fields = fields

    def get_roles(self, obj: User) -> list[str]:
        return list(obj.roles.values_list("code", flat=True))


class UserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    role_codes = serializers.ListField(
        child=serializers.ChoiceField(choices=RoleCode.choices),
        required=False,
        default=list,
    )


class SignupSerializer(serializers.Serializer):
    org_name = serializers.CharField(max_length=255)
    admin_username = serializers.CharField(max_length=150)
    admin_email = serializers.EmailField(required=False, allow_blank=True)
    admin_password = serializers.CharField(write_only=True, min_length=8)


class TenantTokenSerializer(TokenObtainPairSerializer):
    """Embeds tenant_id and roles into the JWT so the client can read them."""

    @classmethod
    def get_token(cls, user):  # type: ignore[override]
        token = super().get_token(user)
        token["tenant_id"] = str(user.tenant_id) if user.tenant_id else None
        token["roles"] = list(user.roles.values_list("code", flat=True))
        return token
