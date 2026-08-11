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
    """Usuário completo. Só circula em rotas do administrador e no próprio perfil."""

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
            "full_name",
            "cpf",
            "birth_date",
            "phone",
            "is_active",
            "roles",
            "date_joined",
        ]
        read_only_fields = fields

    def get_roles(self, obj: User) -> list[str]:
        return list(obj.roles.values_list("code", flat=True))


class UserUpdateSerializer(serializers.Serializer):
    """Edição de usuário pelo administrador. Todos os campos são opcionais."""

    username = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    nome_guerra = serializers.CharField(max_length=60, required=False, allow_blank=True)
    posto_graduacao = serializers.CharField(max_length=60, required=False, allow_blank=True)
    cpf = serializers.CharField(max_length=14, required=False, allow_blank=True)
    birth_date = serializers.DateField(required=False, allow_null=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    role_codes = serializers.ListField(
        child=serializers.ChoiceField(choices=RoleCode.choices), required=False
    )

    def validate_cpf(self, value: str) -> str:
        if not value:
            return ""
        digits = re.sub(r"\D", "", value)
        if not _cpf_is_valid(digits):
            raise serializers.ValidationError("CPF inválido.")
        return digits


class PasswordResetSerializer(serializers.Serializer):
    """Administrador define uma nova senha para outro usuário."""

    new_password = serializers.CharField(write_only=True, min_length=8)


class MeUpdateSerializer(serializers.Serializer):
    """Campos que o próprio usuário pode alterar."""

    email = serializers.EmailField(required=False)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    nome_guerra = serializers.CharField(max_length=60, required=False, allow_blank=True)
    posto_graduacao = serializers.CharField(max_length=60, required=False, allow_blank=True)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)


class UserCreateSerializer(serializers.Serializer):
    """Cadastro feito pelo administrador — é a única porta de entrada de usuários."""

    username = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    password = serializers.CharField(
        write_only=True, min_length=8, required=False, allow_blank=True, default=""
    )
    # False = pessoa sem acesso ao sistema (só existe para reserva/cautela e histórico).
    is_active = serializers.BooleanField(required=False, default=True)
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    nome_guerra = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    posto_graduacao = serializers.CharField(
        max_length=60, required=False, allow_blank=True, default=""
    )
    cpf = serializers.CharField(max_length=14, required=False, allow_blank=True, default="")
    birth_date = serializers.DateField(required=False, allow_null=True, default=None)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    role_codes = serializers.ListField(
        child=serializers.ChoiceField(choices=RoleCode.choices),
        required=False,
        default=list,
    )

    def validate_email(self, value: str) -> str:
        email = value.strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Já existe um cadastro com este e-mail.")
        return email

    def validate_cpf(self, value: str) -> str:
        if not value:
            return ""
        digits = re.sub(r"\D", "", value)
        if not _cpf_is_valid(digits):
            raise serializers.ValidationError("CPF inválido.")
        if User.objects.filter(cpf=digits).exists():
            raise serializers.ValidationError("Já existe um cadastro com este CPF.")
        return digits

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("is_active", True):
            # Sem acesso: não precisa de login nem senha — o service gera o username.
            if not attrs.get("full_name") and not attrs.get("nome_guerra"):
                raise serializers.ValidationError(
                    {"full_name": "Informe o nome da pessoa."}
                )
            return attrs
        if not attrs.get("password"):
            raise serializers.ValidationError({"password": "Este campo é obrigatório."})
        # Sem login explícito, o e-mail é o usuário (mesma regra do login por e-mail).
        if not attrs.get("username"):
            if not attrs.get("email"):
                raise serializers.ValidationError(
                    {"email": "Informe o e-mail (usado como login) ou um nome de usuário."}
                )
            attrs["username"] = attrs["email"]
        return attrs


class SignupSerializer(serializers.Serializer):
    """Auto-cadastro público (login por e-mail). Conta já nasce ativa."""

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
