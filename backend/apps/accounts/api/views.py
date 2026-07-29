"""Auth/account HTTP layer. Delegates to services; no business logic here."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from core.context import set_current_tenant_id
from core.permissions import HasAnyRole

from ..models import RoleCode
from ..services import OnboardingService, UserService
from .serializers import (
    SignupSerializer,
    TenantTokenSerializer,
    UserCreateSerializer,
    UserSerializer,
)


class TenantTokenView(TokenObtainPairView):
    serializer_class = TenantTokenSerializer


class SignupView(APIView):
    permission_classes = [AllowAny]
    service = OnboardingService()

    @extend_schema(request=SignupSerializer, responses={201: UserSerializer})
    def post(self, request: Request) -> Response:
        payload = SignupSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        tenant, admin = self.service.create_organization(**payload.validated_data)
        return Response(
            {
                "tenant": {"id": str(tenant.id), "name": tenant.name},
                "admin": UserSerializer(admin).data,
            },
            status=201,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserSerializer)
    def get(self, request: Request) -> Response:
        return Response(UserSerializer(request.user).data)


class UserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
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
        return self.service.users.all()

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        payload = UserCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        user = self.service.create_user(
            tenant_id=getattr(request.user, "tenant_id", None),
            actor_id=getattr(request.user, "id", None),
            **payload.validated_data,
        )
        return Response(UserSerializer(user).data, status=201)
