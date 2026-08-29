"""Financeiro HTTP layer. Regras no FinanceService; sem lógica aqui."""
from __future__ import annotations

from datetime import datetime

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import RoleCode
from core.exceptions import BusinessRuleError
from core.viewsets import TenantContextAPIView, TenantScopedViewSet

from ..models import BillingProfile, Due
from ..services import FinanceService
from .serializers import (
    ActivateBillingSerializer,
    BillingProfileSerializer,
    DueSerializer,
    RegisterPaymentSerializer,
    UpdateDueDaySerializer,
)

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


class DueViewSet(TenantScopedViewSet):
    serializer_class = DueSerializer
    queryset = Due.objects.none()
    service = FinanceService()
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):  # type: ignore[override]
        if not _can_read(self.request.user):
            raise BusinessRuleError("Sem permissão para ver o financeiro.", code="forbidden")
        qs = self.service.dues.all().select_related("billing_profile__user")
        profile = self.request.query_params.get("billing_profile")
        user = self.request.query_params.get("user")
        status_f = self.request.query_params.get("status")
        if profile:
            qs = qs.filter(billing_profile_id=profile)
        if user:
            qs = qs.filter(billing_profile__user_id=user)
        if status_f:
            qs = qs.filter(status=status_f)
        return qs.order_by("period")

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        raise MethodNotAllowed(request.method)

    @extend_schema(request=RegisterPaymentSerializer, responses={200: DueSerializer(many=True)})
    @action(detail=False, methods=["post"], url_path="registrar-pagamento")
    def registrar_pagamento(self, request: Request) -> Response:
        if not _can_manage(request.user):
            raise BusinessRuleError("Apenas Administrador registra pagamento.", code="forbidden")
        payload = RegisterPaymentSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        dues = self.service.register_payment(
            user=payload.validated_data["user"],
            amount=payload.validated_data["amount"],
            method=payload.validated_data["method"],
            paid_at=payload.validated_data["paid_at"],
            actor_id=str(request.user.pk),
        )
        return Response(DueSerializer(dues, many=True).data)

    @extend_schema(responses={200: DueSerializer(many=True)})
    @action(detail=True, methods=["post"], url_path="cancelar-pagamento")
    def cancelar_pagamento(self, request: Request, pk: str = "") -> Response:
        if not _can_manage(request.user):
            raise BusinessRuleError("Apenas Administrador cancela pagamento.", code="forbidden")
        due = self.get_object()
        dues = self.service.cancel_payment(due_id=due.pk, actor_id=str(request.user.pk))
        return Response(DueSerializer(dues, many=True).data)


class FinanceDashboardView(TenantContextAPIView):
    """Indicadores agregados do financeiro, para o painel do admin."""

    permission_classes = [IsAuthenticated]
    service = FinanceService()

    def get(self, request: Request) -> Response:
        if not _can_read(request.user):
            raise BusinessRuleError("Sem permissão para ver o financeiro.", code="forbidden")
        raw_from = request.query_params.get("from")
        raw_to = request.query_params.get("to")
        date_from = datetime.strptime(raw_from, "%Y-%m-%d").date() if raw_from else None
        date_to = datetime.strptime(raw_to, "%Y-%m-%d").date() if raw_to else None
        return Response(self.service.dashboard(date_from=date_from, date_to=date_to))


class MyFinanceView(TenantContextAPIView):
    """Situação financeira de quem está logado."""

    permission_classes = [IsAuthenticated]
    service = FinanceService()

    def get(self, request: Request) -> Response:
        profile = self.service.profiles.profile_for_user(request.user.pk)
        if profile is None or not profile.is_active:
            return Response(status=404)
        return Response(self.service.summary_for(profile))
