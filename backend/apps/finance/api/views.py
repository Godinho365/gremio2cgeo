"""Financeiro HTTP layer. Regras no FinanceService; sem lógica aqui."""
from __future__ import annotations

from datetime import datetime

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import RoleCode
from core.exceptions import BusinessRuleError
from core.viewsets import TenantContextAPIView, TenantScopedViewSet

from apps.payments.api.serializers import PaymentSerializer

from ..models import BillingProfile, Due, FinancialStatus, PlanCode
from ..services import FinanceService
from .serializers import (
    ActivateBillingSerializer,
    AssociadoInviteSerializer,
    BillingProfileSerializer,
    DueSerializer,
    GenerateInviteSerializer,
    InitiatePixPaymentSerializer,
    RegisterPaymentSerializer,
    UpdateDueDaySerializer,
)

_READ_ROLES = (RoleCode.ADMIN, RoleCode.DIRECTOR, RoleCode.INVENTORY, RoleCode.AUDITOR)
_MANAGE_ROLES = (RoleCode.ADMIN,)
_INVITE_BLOCKING_STATUSES = (FinancialStatus.OVERDUE, FinancialStatus.DELINQUENT)


def _can_read(user) -> bool:
    return user.is_superuser or user.roles.filter(code__in=_READ_ROLES).exists()


def _can_manage(user) -> bool:
    return user.is_superuser or user.roles.filter(code__in=_MANAGE_ROLES).exists()


def _can_invite_associado(user, service: FinanceService) -> bool:
    """Quem convida Cb/Sd EP pro Associado Full: Administrador, ou qualquer
    Associado Full que esteja em dia (mesma régua de "em dia" já usada pra
    reservar patrimônio e cortar pela assinatura da barbearia)."""
    if _can_manage(user):
        return True
    profile = service.profiles.profile_for_user(user.pk)
    return (
        profile is not None
        and profile.is_active
        and profile.plan == PlanCode.ASSOCIADO
        and profile.financial_status not in _INVITE_BLOCKING_STATUSES
    )


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
            plan=payload.validated_data["plan"],
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


class AssociadoInviteListCreateView(TenantContextAPIView):
    permission_classes = [IsAuthenticated]
    service = FinanceService()

    def get(self, request: Request) -> Response:
        if not _can_read(request.user):
            raise BusinessRuleError("Sem permissão para ver o financeiro.", code="forbidden")
        invites = self.service.list_pending_associado_invites()
        return Response(AssociadoInviteSerializer(invites, many=True).data)

    def post(self, request: Request) -> Response:
        if not _can_invite_associado(request.user, self.service):
            raise BusinessRuleError(
                "Apenas Administrador ou Associado Full em dia gera convites.",
                code="forbidden",
            )
        payload = GenerateInviteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        invite = self.service.generate_associado_invite(
            user=payload.validated_data["user"], actor_id=str(request.user.pk)
        )
        return Response(AssociadoInviteSerializer(invite).data, status=201)


class AssociadoInviteCandidatesView(TenantContextAPIView):
    """Busca limitada pra quem convida sem ser Admin: só nome/posto de quem
    já é candidato de verdade — não expõe o cadastro completo (`/api/users`
    continua admin-only)."""

    permission_classes = [IsAuthenticated]
    service = FinanceService()

    def get(self, request: Request) -> Response:
        if not _can_invite_associado(request.user, self.service):
            raise BusinessRuleError(
                "Apenas Administrador ou Associado Full em dia busca candidatos.",
                code="forbidden",
            )
        query = request.query_params.get("q", "")
        candidates = self.service.search_associado_invite_candidates(query=query)
        return Response(
            [
                {
                    "id": str(u.id),
                    "display_name": u.display_name,
                    "posto_graduacao": u.posto_graduacao,
                }
                for u in candidates
            ]
        )


class AssociadoInviteAcceptView(TenantContextAPIView):
    permission_classes = [IsAuthenticated]
    service = FinanceService()

    def post(self, request: Request, token: str = "") -> Response:
        profile = self.service.accept_associado_invite(token=token, actor=request.user)
        return Response(BillingProfileSerializer(profile).data)


class MyFinanceView(TenantContextAPIView):
    """Situação financeira de quem está logado."""

    permission_classes = [IsAuthenticated]
    service = FinanceService()

    def get(self, request: Request) -> Response:
        profile = self.service.profiles.profile_for_user(request.user.pk)
        if profile is None or not profile.is_active:
            return Response(status=404)
        return Response(self.service.summary_for(profile))


class SelfSubscribeView(TenantContextAPIView):
    """Autoatendimento: o próprio usuário ativa um plano do financeiro sem
    depender do administrador — Associado Full ou Assinatura Barbearia,
    conforme o que o posto permitir.

    A elegibilidade (`_assert_eligible` dentro de `activate_billing`) já
    recusa sozinha quem não pode assinar o plano escolhido — não precisa
    duplicar a checagem aqui.
    """

    permission_classes = [IsAuthenticated]
    service = FinanceService()

    def post(self, request: Request) -> Response:
        plan = request.data.get("plan")
        if plan not in PlanCode.values:
            raise BusinessRuleError("Escolha um plano válido.", code="invalid_plan")
        today = timezone.localdate()
        profile = self.service.activate_billing(
            user=request.user,
            plan=plan,
            due_day=today.day,
            started_period=today.replace(day=1),
            actor_id=str(request.user.pk),
        )
        return Response(BillingProfileSerializer(profile).data, status=201)


class InitiatePixPaymentView(TenantContextAPIView):
    """Autoatendimento: o próprio usuário abre um Pix pra pagar a mensalidade."""

    permission_classes = [IsAuthenticated]
    service = FinanceService()

    def post(self, request: Request) -> Response:
        payload = InitiatePixPaymentSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        payment = self.service.initiate_pix_payment(
            user=request.user,
            amount=payload.validated_data["amount"],
            actor_id=str(request.user.pk),
        )
        return Response(PaymentSerializer(payment).data, status=201)


class FinancePixStatusView(TenantContextAPIView):
    """Reconsulta o Pix da mensalidade — a tela do QR usa isto pra confirmar
    sozinha, sem depender só do webhook."""

    permission_classes = [IsAuthenticated]
    service = FinanceService()

    def get(self, request: Request, payment_id: str = "") -> Response:
        payment = self.service.refresh_pix_payment(user=request.user, payment_id=payment_id)
        if payment is None:
            return Response(status=404)
        return Response(PaymentSerializer(payment).data)
