"""Barbearia HTTP layer. Tudo que é regra passa pelo BarbershopService."""
from __future__ import annotations

from datetime import date, datetime

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import RoleCode
from core.exceptions import BusinessRuleError
from core.viewsets import TenantContextAPIView, TenantScopedViewSet

from ..models import Appointment, AppointmentStatus, Barber
from ..services import BarbershopService
from .serializers import (
    AppointmentCreateSerializer,
    AppointmentSerializer,
    BarberSerializer,
    BarberTimeOffSerializer,
    BarberWriteSerializer,
    QuotaSerializer,
    ReplicateScheduleSerializer,
    RescheduleSerializer,
    ScheduleWriteSerializer,
    SlotSerializer,
    TimeOffWriteSerializer,
)

# Quem administra a barbearia: o admin do sistema e o perfil próprio do módulo.
_MANAGE_ROLES = (RoleCode.ADMIN, RoleCode.BARBERSHOP)


def _is_manager(user) -> bool:
    return user.is_superuser or user.roles.filter(code__in=_MANAGE_ROLES).exists()


def _require_manager(user, what: str) -> None:
    if not _is_manager(user):
        raise BusinessRuleError(
            f"Apenas a administração da barbearia pode {what}.", code="forbidden"
        )


def _parse_date(raw: str | None) -> date:
    if not raw:
        return timezone.localdate()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise BusinessRuleError("Data inválida. Use AAAA-MM-DD.", code="invalid_date") from None


class BarberViewSet(TenantScopedViewSet):
    """Cadastro do barbeiro. Leitura: qualquer usuário; escrita: administração."""

    serializer_class = BarberSerializer
    queryset = Barber.objects.none()
    service = BarbershopService()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):  # type: ignore[override]
        qs = self.service.barbers.all().prefetch_related("schedules", "time_off")
        if self.request.query_params.get("active") in ("1", "true"):
            qs = qs.filter(is_active=True)
        return qs.order_by("name")

    def list(self, request: Request, *args: object, **kwargs: object) -> Response:
        """`?date=AAAA-MM-DD` devolve só quem atende naquele dia (passo 2 do fluxo)."""
        qs = self.filter_queryset(self.get_queryset())
        raw_date = request.query_params.get("date")
        if raw_date:
            day = _parse_date(raw_date)
            qs = [b for b in qs if self.service.works_on(barber_id=b.id, day=day)]
        page = self.paginate_queryset(qs)
        serializer = BarberSerializer(page if page is not None else qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(request=BarberWriteSerializer, responses={201: BarberSerializer})
    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        _require_manager(request.user, "cadastrar barbeiros")
        payload = BarberWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        barber = self.service.create_barber(actor_id=str(request.user.pk), **payload.validated_data)
        return Response(BarberSerializer(barber).data, status=201)

    @extend_schema(request=BarberWriteSerializer, responses={200: BarberSerializer})
    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        _require_manager(request.user, "editar barbeiros")
        payload = BarberWriteSerializer(
            data=request.data, partial=bool(kwargs.get("partial", False))
        )
        payload.is_valid(raise_exception=True)
        barber = self.service.update_barber(
            barber_id=self.get_object().pk, actor_id=str(request.user.pk), **payload.validated_data
        )
        return Response(BarberSerializer(barber).data)

    def partial_update(self, request: Request, *args: object, **kwargs: object) -> Response:
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        _require_manager(request.user, "excluir barbeiros")
        self.service.delete_barber(
            barber_id=self.get_object().pk, actor_id=str(request.user.pk)
        )
        return Response(status=204)

    @extend_schema(request=ScheduleWriteSerializer, responses={200: BarberSerializer})
    @action(detail=True, methods=["put"], url_path="horarios")
    def schedule(self, request: Request, pk: str = "") -> Response:
        """Substitui a grade semanal inteira do barbeiro."""
        _require_manager(request.user, "definir os horários de trabalho")
        payload = ScheduleWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        self.service.set_schedule(
            barber_id=pk,
            windows=list(payload.validated_data["windows"]),
            actor_id=str(request.user.pk),
        )
        return Response(BarberSerializer(self.service.barbers.get(pk)).data)

    @extend_schema(request=TimeOffWriteSerializer, responses={201: BarberTimeOffSerializer})
    @action(detail=True, methods=["post"], url_path="folgas")
    def add_time_off(self, request: Request, pk: str = "") -> Response:
        """Folga de um dia ou de um período (RN-BB10)."""
        _require_manager(request.user, "lançar folgas")
        payload = TimeOffWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        off = self.service.add_time_off(
            barber_id=pk,
            start_date=payload.validated_data["start_date"],
            end_date=payload.validated_data.get("end_date"),
            reason=payload.validated_data.get("reason", ""),
            actor_id=str(request.user.pk),
        )
        return Response(BarberTimeOffSerializer(off).data, status=201)

    @extend_schema(
        request=ReplicateScheduleSerializer, responses={200: BarberSerializer(many=True)}
    )
    @action(detail=True, methods=["post"], url_path="horarios/replicar")
    def replicate_schedule(self, request: Request, pk: str = "") -> Response:
        """Aplica a grade deste barbeiro nos barbeiros indicados (RN-BB11)."""
        _require_manager(request.user, "replicar horários")
        payload = ReplicateScheduleSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        quantos = self.service.replicate_schedule(
            source_id=pk,
            target_ids=list(payload.validated_data["targets"]),
            actor_id=str(request.user.pk),
        )
        return Response({"updated": quantos})

    @action(detail=True, methods=["delete"], url_path="folgas/(?P<off_id>[^/.]+)")
    def remove_time_off(self, request: Request, pk: str = "", off_id: str = "") -> Response:
        _require_manager(request.user, "remover folgas")
        self.service.remove_time_off(time_off_id=off_id, actor_id=str(request.user.pk))
        return Response(status=204)

    @extend_schema(responses={200: SlotSerializer(many=True)})
    @action(detail=True, methods=["get"], url_path="horarios-livres")
    def slots(self, request: Request, pk: str = "") -> Response:
        """Horários que ainda dá para marcar com este barbeiro no dia pedido."""
        day = _parse_date(request.query_params.get("date"))
        slots = self.service.available_slots(barber_id=pk, day=day)
        return Response(SlotSerializer(slots, many=True).data)


class AppointmentViewSet(TenantScopedViewSet):
    serializer_class = AppointmentSerializer
    queryset = Appointment.objects.none()
    service = BarbershopService()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):  # type: ignore[override]
        qs = self.service.appointments.all().select_related("barber", "customer")
        user = self.request.user
        # Cliente só enxerga os próprios horários; a administração vê todos.
        scope = self.request.query_params.get("scope", "mine")
        if scope == "mine" or not _is_manager(user):
            qs = qs.filter(customer_id=user.pk)

        barber = self.request.query_params.get("barber")
        if barber:
            qs = qs.filter(barber_id=barber)
        raw_date = self.request.query_params.get("date")
        if raw_date:
            qs = qs.filter(start_at__date=_parse_date(raw_date))
        status_f = self.request.query_params.get("status")
        if status_f:
            qs = qs.filter(status=status_f)
        if self.request.query_params.get("upcoming") in ("1", "true"):
            qs = qs.filter(start_at__gte=timezone.now(), status=AppointmentStatus.SCHEDULED)
            return qs.order_by("start_at")
        return qs.order_by("-start_at")

    @extend_schema(request=AppointmentCreateSerializer, responses={201: AppointmentSerializer})
    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        payload = AppointmentCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        customer_id = payload.validated_data.get("customer")
        if customer_id and str(customer_id) != str(request.user.pk):
            _require_manager(request.user, "marcar em nome de outra pessoa")
        appointment = self.service.book(
            barber_id=payload.validated_data["barber"],
            customer_id=str(customer_id or request.user.pk),
            start_at=payload.validated_data["start_at"],
            notes=payload.validated_data.get("notes", ""),
            actor_id=str(request.user.pk),
        )
        return Response(AppointmentSerializer(appointment).data, status=201)

    def _assert_owner_or_manager(self, appointment: Appointment, what: str) -> None:
        if appointment.customer_id != self.request.user.pk and not _is_manager(self.request.user):
            raise BusinessRuleError(f"Sem permissão para {what}.", code="forbidden")

    @extend_schema(request=RescheduleSerializer, responses={200: AppointmentSerializer})
    @action(detail=True, methods=["post"], url_path="remarcar")
    def reschedule(self, request: Request, pk: str = "") -> Response:
        self._assert_owner_or_manager(self.service.appointments.get(pk), "remarcar este horário")
        payload = RescheduleSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        appointment = self.service.reschedule(
            appointment_id=pk,
            start_at=payload.validated_data["start_at"],
            barber_id=payload.validated_data.get("barber"),
            actor_id=str(request.user.pk),
            # A janela de 10 minutos vale para o cliente; a administração ainda
            # precisa poder acertar a agenda em cima da hora.
            enforce_cutoff=not _is_manager(request.user),
        )
        return Response(AppointmentSerializer(appointment).data)

    @extend_schema(responses={200: AppointmentSerializer})
    @action(detail=True, methods=["post"], url_path="cancelar")
    def cancel(self, request: Request, pk: str = "") -> Response:
        self._assert_owner_or_manager(self.service.appointments.get(pk), "cancelar este horário")
        appointment = self.service.cancel(
            appointment_id=pk,
            actor_id=str(request.user.pk),
            enforce_cutoff=not _is_manager(request.user),
        )
        return Response(AppointmentSerializer(appointment).data)

    @extend_schema(responses={200: AppointmentSerializer})
    @action(detail=True, methods=["post"], url_path="concluir")
    def finish(self, request: Request, pk: str = "") -> Response:
        _require_manager(request.user, "encerrar atendimentos")
        appointment = self.service.finish(
            appointment_id=pk,
            actor_id=str(request.user.pk),
            no_show=request.data.get("no_show") in (True, "1", "true"),
        )
        return Response(AppointmentSerializer(appointment).data)

    @extend_schema(responses={200: AppointmentSerializer})
    @action(detail=True, methods=["get"], url_path="pagamento")
    def payment_status(self, request: Request, pk: str = "") -> Response:
        """Reconsulta o Pix no provedor e devolve o agendamento já atualizado.

        É o caminho que funciona mesmo sem o webhook chegar (instalação em rede
        interna, por exemplo): a tela do QR pergunta aqui de tempos em tempos.
        """
        appointment = self.service.appointments.get(pk)
        self._assert_owner_or_manager(appointment, "ver este pagamento")
        return Response(AppointmentSerializer(self.service.refresh_payment(appointment)).data)

    @extend_schema(responses={200: QuotaSerializer})
    @action(detail=False, methods=["get"], url_path="cota")
    def quota(self, request: Request) -> Response:
        """Quantos cortes de assinante a pessoa ainda tem no mês da data pedida."""
        day = _parse_date(request.query_params.get("date"))
        customer_id = request.query_params.get("customer")
        if customer_id and str(customer_id) != str(request.user.pk):
            _require_manager(request.user, "consultar a cota de outra pessoa")
        quota = self.service.subscriber_quota(
            customer_id=customer_id or str(request.user.pk), day=day
        )
        return Response(QuotaSerializer(quota).data)


class PublicAgendaLinkView(TenantContextAPIView):
    """Gera/consulta o link público da agenda do dia — só a administração
    da barbearia. `POST` cria (ou reaproveita) o link atual; `PATCH`
    revoga o antigo e gera um novo."""

    permission_classes = [IsAuthenticated]
    service = BarbershopService()

    def post(self, request: Request) -> Response:
        _require_manager(request.user, "gerar o link público da agenda")
        link = self.service.get_or_create_public_agenda_link(actor_id=str(request.user.pk))
        return Response({"token": link.token})

    def patch(self, request: Request) -> Response:
        _require_manager(request.user, "regenerar o link público da agenda")
        link = self.service.regenerate_public_agenda_link(actor_id=str(request.user.pk))
        return Response({"token": link.token})


class PublicAgendaView(APIView):
    """Agenda do dia sem login — o tenant vem do token da URL (RN-BB12).
    Não usa TenantContextAPIView de propósito: não há usuário autenticado
    aqui, então não há tenant de sessão pra fixar."""

    permission_classes = [AllowAny]

    def get(self, request: Request, token: str = "") -> Response:
        agenda = BarbershopService.today_agenda_by_token(token=token)
        if agenda is None:
            raise BusinessRuleError("Link inválido ou revogado.", code="invalid_public_link")
        return Response(agenda)
