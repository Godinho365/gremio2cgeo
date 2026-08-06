from __future__ import annotations

import re

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from ..models import RoleCode, User


def _cpf_is_valid(digits: str) -> bool:
    """Valida CPF pelos dígitos verificadores (11 dígitos)."""
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    for length in (9, 10):
        total = sum(int(digits[i]) * ((length + 1) - i) for i in range(length))
        check = (total * 10 % 11) % 10
        if check != int(digits[length]):
            return False
    return True


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "nome_guerra",
            "posto_graduacao",
            "display_name",
            "is_active",
            "roles",
            "date_joined",
        ]
        read_only_fields = fields

    def get_roles(self, obj: User) -> list[str]:
        return list(obj.roles.values_list("code", flat=True))


class UserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    nome_guerra = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    posto_graduacao = serializers.CharField(
        max_length=60, required=False, allow_blank=True, default=""
    )
    role_codes = serializers.ListField(
        child=serializers.ChoiceField(choices=RoleCode.choices),
        required=False,
        default=list,
    )


class SignupSerializer(serializers.Serializer):
    """Auto-cadastro de usuário (login por e-mail)."""

    full_name = serializers.CharField(max_length=255)
    nome_guerra = serializers.CharField(max_length=60)
    posto_graduacao = serializers.CharField(max_length=60)
    cpf = serializers.CharField(max_length=14)
    birth_date = serializers.DateField()
    email = serializers.EmailField()
    email_confirm = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_cpf(self, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if not _cpf_is_valid(digits):
            raise serializers.ValidationError("CPF inválido.")
        if User.objects.filter(cpf=digits).exists():
            raise serializers.ValidationError("Já existe um cadastro com este CPF.")
        return digits

    def validate_email(self, value: str) -> str:
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Já existe um cadastro com este e-mail.")
        return email

    def validate(self, attrs: dict) -> dict:
        if attrs["email"] != attrs.get("email_confirm", "").strip().lower():
            raise serializers.ValidationError({"email_confirm": "Os e-mails não conferem."})
        attrs.pop("email_confirm", None)
        return attrs


class TenantTokenSerializer(TokenObtainPairSerializer):
    """Embeds tenant_id and roles into the JWT. Aceita login por e-mail ou usuário."""

    def validate(self, attrs: dict) -> dict:
        login = attrs.get(self.username_field, "")
        if login and "@" in login:
            match = User.objects.filter(email__iexact=login).first()
            if match:
                attrs[self.username_field] = match.username
        return super().validate(attrs)

    @classmethod
    def get_token(cls, user):  # type: ignore[override]
        token = super().get_token(user)
        token["tenant_id"] = str(user.tenant_id) if user.tenant_id else None
        token["roles"] = list(user.roles.values_list("code", flat=True))
        return token
