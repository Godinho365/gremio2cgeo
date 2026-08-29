"""Financeiro HTTP layer. Regras no FinanceService; sem lógica aqui."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import RoleCode
from core.exceptions import BusinessRuleError
from core.viewsets import TenantScopedViewSet

from ..models import BillingProfile
from ..services import FinanceService
from .serializers import ActivateBillingSerializer, BillingProfileSerializer, UpdateDueDaySerializer

_READ_ROLES = (RoleCode.ADMIN, RoleCode.DIRECTOR, RoleCode.INVENTORY, RoleCode.AUDITOR)
_MANAGE_ROLES = (RoleCode.ADMIN,)


def _can_read(user) -> bool:
    return user.is_superuser or user.roles.filter(code__in=_READ_ROLES).exists()


def _can_manage(user) -> bool:
    return user.is_superuser or user.roles.filter(code__in=_MANAGE_ROLES).exists()


class BillingProfileViewSet(TenantScopedViewSet):
    serializer_class = BillingProfileSerializer
    queryset = BillingProfile.objects.none()
    service = FinanceService()
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):  # type: ignore[override]
        if not _can_read(self.request.user):
            raise BusinessRuleError("Sem permissão para ver o financeiro.", code="forbidden")
        return self.service.profiles.all().select_related("user").order_by("user__nome_guerra")

    @extend_schema(request=ActivateBillingSerializer, responses={201: BillingProfileSerializer})
    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        if not _can_manage(request.user):
            raise BusinessRuleError("Apenas Administrador ativa cobrança.", code="forbidden")
        payload = ActivateBillingSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        profile = self.service.activate_billing(
            user=payload.validated_data["user"],
            due_day=payload.validated_data["due_day"],
            started_period=payload.validated_data["started_period"],
            actor_id=str(request.user.pk),
        )
        return Response(BillingProfileSerializer(profile).data, status=201)

    @extend_schema(request=UpdateDueDaySerializer, responses={200: BillingProfileSerializer})
    def partial_update(self, request: Request, *args: object, **kwargs: object) -> Response:
        if not _can_manage(request.user):
            raise BusinessRuleError("Apenas Administrador edita o vencimento.", code="forbidden")
        payload = UpdateDueDaySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        profile = self.service.update_due_day(
            profile=self.get_object(),
            due_day=payload.validated_data["due_day"],
            actor_id=str(request.user.pk),
        )
        return Response(BillingProfileSerializer(profile).data)

    @extend_schema(responses={200: BillingProfileSerializer})
    @action(detail=True, methods=["post"], url_path="desativar")
    def desativar(self, request: Request, pk: str = "") -> Response:
        if not _can_manage(request.user):
            raise BusinessRuleError("Apenas Administrador desativa cobrança.", code="forbidden")
        profile = self.service.deactivate_billing(
            profile=self.get_object(), actor_id=str(request.user.pk)
        )
        return Response(BillingProfileSerializer(profile).data)
