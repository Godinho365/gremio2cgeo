"""Auth/account HTTP layer. Delegates to services; no business logic here."""
from __future__ import annotations

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from core.context import set_current_tenant_id
from core.permissions import HasAnyRole
from core.viewsets import TenantContextAPIView

from ..models import RoleCode
from ..services import UserService
from .serializers import (
    MeUpdateSerializer,
    PasswordChangeSerializer,
    PasswordResetSerializer,
    SignupSerializer,
    TenantTokenSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)


class TenantTokenView(TokenObtainPairView):
    serializer_class = TenantTokenSerializer


class SignupView(APIView):
    """Auto-cadastro público de usuário — entra direto, sem aprovação."""

    permission_classes = [AllowAny]
    service = UserService()

    @extend_schema(request=SignupSerializer, responses={201: UserSerializer})
    def post(self, request: Request) -> Response:
        payload = SignupSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        user = self.service.self_register(**payload.validated_data)
        return Response(UserSerializer(user).data, status=201)


class MeView(TenantContextAPIView):
    permission_classes = [IsAuthenticated]
    service = UserService()

    @extend_schema(responses=UserSerializer)
    def get(self, request: Request) -> Response:
        return Response(UserSerializer(request.user).data)

    @extend_schema(request=MeUpdateSerializer, responses=UserSerializer)
    def patch(self, request: Request) -> Response:
        payload = MeUpdateSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        user = self.service.update_profile(user=request.user, **payload.validated_data)
        return Response(UserSerializer(user).data)


class MePasswordView(TenantContextAPIView):
    """Troca de senha do próprio usuário."""

    permission_classes = [IsAuthenticated]
    service = UserService()

    @extend_schema(request=PasswordChangeSerializer, responses={204: None})
    def post(self, request: Request) -> Response:
        payload = PasswordChangeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        self.service.change_password(user=request.user, **payload.validated_data)
        return Response(status=204)


class UserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Tenant-scoped user management. Admin only."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = (RoleCode.ADMIN,)
    service = UserService()

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        set_current_tenant_id(getattr(request.user, "tenant_id", None))

    def get_queryset(self):  # type: ignore[override]
        qs = self.service.users.all()
        params = self.request.query_params
        search = (params.get("q") or "").strip()
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(full_name__icontains=search)
                | Q(nome_guerra__icontains=search)
                | Q(posto_graduacao__icontains=search)
            )
        role = params.get("role")
        if role:
            qs = qs.filter(roles__code=role)
        active = params.get("is_active")
        if active in ("true", "1"):
            qs = qs.filter(is_active=True)
        elif active in ("false", "0"):
            qs = qs.filter(is_active=False)
        return qs.distinct()

    @extend_schema(request=UserUpdateSerializer, responses={200: UserSerializer})
    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        payload = UserUpdateSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        user = self.service.update_user(
            user=self.get_object(), actor=request.user, **payload.validated_data
        )
        return Response(UserSerializer(user).data)

    def partial_update(self, request: Request, *args: object, **kwargs: object) -> Response:
        return self.update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        self.service.delete_user(user=self.get_object(), actor=request.user)
        return Response(status=204)

    @extend_schema(request=PasswordResetSerializer, responses={204: None})
    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request: Request, pk: str = "") -> Response:
        payload = PasswordResetSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        self.service.reset_password(
            user=self.get_object(),
            actor=request.user,
            new_password=payload.validated_data["new_password"],
        )
        return Response(status=204)

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        payload = UserCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        user = self.service.create_user(
            tenant_id=getattr(request.user, "tenant_id", None),
            actor_id=getattr(request.user, "id", None),
            **payload.validated_data,
        )
        return Response(UserSerializer(user).data, status=201)
