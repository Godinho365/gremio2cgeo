"""Contratos da barbearia. Sem regra de negócio — isso é do BarbershopService."""
from __future__ import annotations

from rest_framework import serializers

from apps.payments.api.serializers import PaymentSerializer

from ..models import Appointment, AppointmentStatus, Barber, BarberSchedule, BarberTimeOff
from ..services import BarbershopService


class BarberScheduleSerializer(serializers.ModelSerializer):
    weekday_label = serializers.CharField(source="get_weekday_display", read_only=True)

    class Meta:
        model = BarberSchedule
        fields = ["id", "weekday", "weekday_label", "start_time", "end_time", "slot_minutes"]
        read_only_fields = ["id"]


class ScheduleWindowSerializer(serializers.Serializer):
    """Uma janela da grade semanal enviada no PUT da agenda do barbeiro."""

    weekday = serializers.IntegerField(min_value=0, max_value=6)
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    slot_minutes = serializers.IntegerField(min_value=5, max_value=240, default=30)


class ScheduleWriteSerializer(serializers.Serializer):
    windows = ScheduleWindowSerializer(many=True)


class BarberTimeOffSerializer(serializers.ModelSerializer):
    days = serializers.IntegerField(read_only=True)

    class Meta:
        model = BarberTimeOff
        fields = ["id", "start_date", "end_date", "days", "reason"]
        read_only_fields = ["id", "days"]


class TimeOffWriteSerializer(serializers.Serializer):
    """Um dia (só `start_date`) ou um período (`start_date` + `end_date`)."""

    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True)


class ReplicateScheduleSerializer(serializers.Serializer):
    """Barbeiros que vão receber a grade deste."""

    targets = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)


class BarberSerializer(serializers.ModelSerializer):
    # Filtrados à mão: a relação crua do Django devolve também o que foi
    # excluído (exclusão aqui é lógica, via deleted_at), e uma folga apagada
    # continuaria aparecendo na tela.
    schedules = serializers.SerializerMethodField()
    time_off = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = Barber
        fields = [
            "id",
            "name",
            "nickname",
            "display_name",
            "phone",
            "photo_data",
            "is_active",
            "schedules",
            "time_off",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_display_name(self, obj: Barber) -> str:
        return obj.nickname or obj.name

    def get_schedules(self, obj: Barber) -> list[dict]:
        janelas = obj.schedules.filter(deleted_at__isnull=True).order_by(
            "weekday", "start_time"
        )
        return BarberScheduleSerializer(janelas, many=True).data

    def get_time_off(self, obj: Barber) -> list[dict]:
        folgas = obj.time_off.filter(deleted_at__isnull=True).order_by("start_date")
        return BarberTimeOffSerializer(folgas, many=True).data


class BarberWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Barber
        fields = ["name", "nickname", "phone", "photo_data", "is_active"]


class SlotSerializer(serializers.Serializer):
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()


class AppointmentSerializer(serializers.ModelSerializer):
    """`status` é a situação pelo relógio (RN-BB7), não o que está gravado."""

    barber_name = serializers.SerializerMethodField()
    customer_name = serializers.CharField(source="customer.display_name", read_only=True)
    status = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    can_change = serializers.SerializerMethodField()
    change_deadline = serializers.SerializerMethodField()
    payment = PaymentSerializer(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "barber",
            "barber_name",
            "customer",
            "customer_name",
            "start_at",
            "end_at",
            "is_subscriber",
            "price",
            "payment",
            "paid_with_credit",
            "status",
            "status_label",
            "can_change",
            "change_deadline",
            "notes",
            "created_at",
        ]
        read_only_fields = fields

    @property
    def _service(self) -> BarbershopService:
        return BarbershopService()

    def get_barber_name(self, obj: Appointment) -> str:
        return obj.barber.nickname or obj.barber.name

    def get_status(self, obj: Appointment) -> str:
        return self._service.effective_status(obj)

    def get_status_label(self, obj: Appointment) -> str:
        return AppointmentStatus(self.get_status(obj)).label

    def get_can_change(self, obj: Appointment) -> bool:
        """Ainda dá para remarcar/cancelar? (RN-BB6)"""
        return self._service.can_change(obj)

    def get_change_deadline(self, obj: Appointment) -> str:
        return self._service.change_deadline(obj).isoformat()


class AppointmentCreateSerializer(serializers.Serializer):
    barber = serializers.UUIDField()
    start_at = serializers.DateTimeField()
    is_subscriber = serializers.BooleanField()
    notes = serializers.CharField(required=False, allow_blank=True)
    # Só a administração da barbearia pode marcar em nome de outra pessoa.
    customer = serializers.UUIDField(required=False, allow_null=True)


class RescheduleSerializer(serializers.Serializer):
    start_at = serializers.DateTimeField()
    barber = serializers.UUIDField(required=False, allow_null=True)


class QuotaSerializer(serializers.Serializer):
    limit = serializers.IntegerField()
    used = serializers.IntegerField()
    remaining = serializers.IntegerField()
