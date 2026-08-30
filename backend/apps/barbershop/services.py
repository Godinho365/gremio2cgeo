"""BarbershopService — regras da barbearia (RN-BB1..BB12).

RN-BB1  Dois agendamentos ativos nunca se sobrepõem para o mesmo barbeiro.
RN-BB2  Só dá para marcar num horário que existe na grade do barbeiro e fora de folga.
RN-BB3  Não se marca no passado.
RN-BB4  Assinante tem SUBSCRIBER_MONTHLY_LIMIT cortes por mês; cancelado devolve o corte.
        Quem é assinante vem do Financeiro (BillingProfile ativo, qualquer
        plano) — nunca do que o cliente manda na requisição.
RN-BB5  Quem não é assinante paga o valor de WALK_IN_PRICE (.env), congelado
        no agendamento — mudar a tabela não altera o que já foi marcado.
RN-BB6  Cliente remarca/cancela até CHANGE_CUTOFF_MINUTES antes da hora marcada.
RN-BB7  A situação do atendimento vem do relógio: Agendado → Ativo → Finalizado.
RN-BB8  Avulso só vira Agendado depois que o Pix é confirmado pelo provedor;
        enquanto isso segura o horário, e vencido o prazo o horário é liberado.
RN-BB9  Cancelar um horário já pago vira crédito no perfil, e o crédito paga
        o próximo corte sem passar pelo Pix.
RN-BB10 Folga é um período; dois períodos do mesmo barbeiro não se sobrepõem.
RN-BB11 A grade de um barbeiro pode ser replicada para outros.
RN-BB12 Agenda pública (sem login) mostra só o dia de hoje, todos os
        barbeiros; um link por organização, revogável a qualquer momento.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.finance.models import FinancialStatus
from apps.finance.repositories import FinanceRepository
from apps.payments.credits import CreditService
from apps.payments.models import CreditReason, Payment, PaymentStatus
from apps.payments.services import PaymentService
from core import audit
from core.context import use_tenant
from core.exceptions import BusinessRuleError, ConflictError
from core.services import BaseService

from .models import (
    ACTIVE_APPOINTMENT_STATUSES,
    CHANGE_CUTOFF_MINUTES,
    SUBSCRIBER_MONTHLY_LIMIT,
    Appointment,
    AppointmentStatus,
    Barber,
    BarberSchedule,
    PublicAgendaLink,
    walk_in_price,
)
from .repositories import (
    AppointmentRepository,
    BarberRepository,
    BarberScheduleRepository,
    BarberTimeOffRepository,
    PublicAgendaLinkRepository,
)

# Situações em que o horário ainda pode ser remarcado ou cancelado.
_CHANGEABLE_STATUSES = (AppointmentStatus.SCHEDULED, AppointmentStatus.AWAITING_PAYMENT)

# Cobranças que não vão virar pagamento: o horário volta para a lista.
_FAILED_PAYMENT_STATUSES = (
    PaymentStatus.EXPIRED,
    PaymentStatus.REJECTED,
    PaymentStatus.CANCELLED,
)


def _public_agenda_entry(appointment: Appointment) -> dict:
    """Projeção mínima pro link público — sem preço, pagamento nem
    is_subscriber: quem abre o link não precisa (nem deveria) ver isso."""
    status = BarbershopService.effective_status(appointment)
    return {
        "barber_name": appointment.barber.nickname or appointment.barber.name,
        "customer_name": appointment.customer.display_name,
        "start_at": appointment.start_at,
        "end_at": appointment.end_at,
        "status": status,
        "status_label": AppointmentStatus(status).label,
    }


class BarbershopService(BaseService):
    def __init__(
        self,
        barbers: BarberRepository | None = None,
        schedules: BarberScheduleRepository | None = None,
        time_off: BarberTimeOffRepository | None = None,
        appointments: AppointmentRepository | None = None,
        payments: PaymentService | None = None,
        credits: CreditService | None = None,
        finance_profiles: FinanceRepository | None = None,
        public_agenda_links: PublicAgendaLinkRepository | None = None,
    ) -> None:
        self.barbers = barbers or BarberRepository()
        self.schedules = schedules or BarberScheduleRepository()
        self.time_off = time_off or BarberTimeOffRepository()
        self.appointments = appointments or AppointmentRepository()
        self.payments = payments or PaymentService()
        self.credits = credits or CreditService()
        self.finance_profiles = finance_profiles or FinanceRepository()
        self.public_agenda_links = public_agenda_links or PublicAgendaLinkRepository()

    # Vencido ou inadimplente perde o corte de assinante até regularizar —
    # continua elegível a avulso normalmente (RN-BB4).
    _SUBSCRIBER_BLOCKING_STATUSES = (FinancialStatus.OVERDUE, FinancialStatus.DELINQUENT)

    def _is_subscriber(self, customer_id: UUID | str) -> bool:
        """Assinante = tem BillingProfile ativo no Financeiro, qualquer plano,
        e está em dia (nem vencido, nem inadimplente)."""
        profile = self.finance_profiles.profile_for_user(customer_id)
        if profile is None or not profile.is_active:
            return False
        return profile.financial_status not in self._SUBSCRIBER_BLOCKING_STATUSES

    # ── Cadastro do barbeiro ────────────────────────────────────────────────

    @transaction.atomic
    def create_barber(self, *, name: str, actor_id: UUID | str, **fields: object) -> Barber:
        if not name.strip():
            raise BusinessRuleError("Informe o nome do barbeiro.", code="name_required")
        barber = self.barbers.create(name=name.strip(), created_by_id=actor_id, **fields)
        audit.record(
            action="barber.created",
            entity_type="Barber",
            entity_id=barber.id,
            actor_id=actor_id,
        )
        return barber

    @transaction.atomic
    def update_barber(
        self, *, barber_id: UUID | str, actor_id: UUID | str, **fields: object
    ) -> Barber:
        barber = self.barbers.get(barber_id)
        for field, value in fields.items():
            setattr(barber, field, value)
        barber.save()
        audit.record(
            action="barber.updated",
            entity_type="Barber",
            entity_id=barber.id,
            actor_id=actor_id,
            diff={k: str(v) for k, v in fields.items() if k != "photo_data"},
        )
        return barber

    @transaction.atomic
    def delete_barber(self, *, barber_id: UUID | str, actor_id: UUID | str) -> None:
        """Só sai se não tiver agendamento futuro — histórico nunca fica órfão."""
        barber = self.barbers.get(barber_id)
        self.release_unpaid()
        pending = self.appointments.query().filter(
            barber_id=barber.id,
            status__in=ACTIVE_APPOINTMENT_STATUSES,
            start_at__gte=timezone.now(),
        )
        if pending.exists():
            raise BusinessRuleError(
                "Este barbeiro ainda tem horários marcados. Cancele-os antes de excluir.",
                code="barber_has_appointments",
            )
        self.barbers.soft_delete(barber)
        audit.record(
            action="barber.deleted",
            entity_type="Barber",
            entity_id=barber.id,
            actor_id=actor_id,
        )

    # ── Grade de trabalho e folgas ──────────────────────────────────────────

    @transaction.atomic
    def set_schedule(
        self, *, barber_id: UUID | str, windows: list[dict], actor_id: UUID | str
    ) -> list[BarberSchedule]:
        """Substitui a grade semanal inteira do barbeiro pelas janelas informadas."""
        barber = self.barbers.get(barber_id)
        for window in windows:
            if window["start_time"] >= window["end_time"]:
                raise BusinessRuleError(
                    "O horário de início deve ser anterior ao de término.",
                    code="invalid_window",
                )
            if window.get("slot_minutes", 30) <= 0:
                raise BusinessRuleError(
                    "A duração do atendimento deve ser maior que zero.", code="invalid_slot"
                )
        self._assert_no_window_overlap(windows)

        self.schedules.for_barber(barber.id).delete()
        created = [
            self.schedules.create(barber_id=barber.id, created_by_id=actor_id, **window)
            for window in windows
        ]
        audit.record(
            action="barber.schedule_set",
            entity_type="Barber",
            entity_id=barber.id,
            actor_id=actor_id,
            diff={"windows": len(created)},
        )
        return created

    @staticmethod
    def _assert_no_window_overlap(windows: list[dict]) -> None:
        by_day: dict[int, list[dict]] = {}
        for window in windows:
            by_day.setdefault(window["weekday"], []).append(window)
        for day_windows in by_day.values():
            ordered = sorted(day_windows, key=lambda w: w["start_time"])
            for previous, current in zip(ordered, ordered[1:], strict=False):
                if current["start_time"] < previous["end_time"]:
                    raise BusinessRuleError(
                        "Há dois períodos sobrepostos no mesmo dia.", code="window_overlap"
                    )

    @transaction.atomic
    def replicate_schedule(
        self, *, source_id: UUID | str, target_ids: list[UUID | str], actor_id: UUID | str
    ) -> int:
        """Copia a grade semanal de um barbeiro para outros (RN-BB11).

        Substitui a grade dos destinos, igual a definir à mão — quem faz isso
        está dizendo "esses atendem no mesmo horário daquele". Folgas não são
        copiadas: elas são de cada pessoa.
        """
        origem = self.barbers.get(source_id)
        janelas = [
            {
                "weekday": w.weekday,
                "start_time": w.start_time,
                "end_time": w.end_time,
                "slot_minutes": w.slot_minutes,
            }
            for w in self.schedules.for_barber(origem.id)
        ]
        if not janelas:
            raise BusinessRuleError(
                "Este barbeiro não tem horários para copiar.", code="empty_schedule"
            )

        copiados = 0
        for target_id in target_ids:
            if str(target_id) == str(origem.id):
                continue  # copiar para si mesmo não faz nada
            destino = self.barbers.get(target_id)
            self.set_schedule(
                barber_id=destino.id, windows=list(janelas), actor_id=actor_id
            )
            audit.record(
                action="barber.schedule_copied",
                entity_type="Barber",
                entity_id=destino.id,
                actor_id=actor_id,
                diff={"de": str(origem), "janelas": len(janelas)},
            )
            copiados += 1
        return copiados

    @transaction.atomic
    def add_time_off(
        self,
        *,
        barber_id: UUID | str,
        start_date: date,
        end_date: date | None = None,
        reason: str = "",
        actor_id: UUID | str,
    ):
        """Lança uma folga de um dia ou de um período (RN-BB10)."""
        barber = self.barbers.get(barber_id)
        end_date = end_date or start_date
        if end_date < start_date:
            raise BusinessRuleError(
                "O último dia da folga não pode ser antes do primeiro.",
                code="invalid_time_off_range",
            )
        if self.time_off.overlapping(
            barber_id=barber.id, start_date=start_date, end_date=end_date
        ).exists():
            raise BusinessRuleError(
                "Já existe folga lançada dentro desse período.", code="already_off"
            )
        off = self.time_off.create(
            barber_id=barber.id,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            created_by_id=actor_id,
        )
        audit.record(
            action="barber.time_off_added",
            entity_type="Barber",
            entity_id=barber.id,
            actor_id=actor_id,
            diff={"de": start_date.isoformat(), "ate": end_date.isoformat()},
        )
        return off

    @transaction.atomic
    def remove_time_off(self, *, time_off_id: UUID | str, actor_id: UUID | str) -> None:
        off = self.time_off.get(time_off_id)
        self.time_off.soft_delete(off)
        audit.record(
            action="barber.time_off_removed",
            entity_type="Barber",
            entity_id=off.barber_id,
            actor_id=actor_id,
            diff={"de": off.start_date.isoformat(), "ate": off.end_date.isoformat()},
        )

    # ── Horários livres ─────────────────────────────────────────────────────

    def works_on(self, *, barber_id: UUID | str, day: date) -> bool:
        if self.time_off.is_off(barber_id=barber_id, day=day):
            return False
        return self.schedules.for_weekday(barber_id=barber_id, weekday=day.weekday()).exists()

    def available_slots(self, *, barber_id: UUID | str, day: date) -> list[dict]:
        """Horários que ainda dá para marcar naquele dia, na ordem do relógio."""
        if self.time_off.is_off(barber_id=barber_id, day=day):
            return []

        self.release_unpaid()  # RN-BB8: Pix vencido não segura mais o horário
        now = timezone.now()
        taken = [
            (a.start_at, a.end_at)
            for a in self.appointments.on_day(barber_id=barber_id, day=day)
        ]
        slots: list[dict] = []
        for window in self.schedules.for_weekday(barber_id=barber_id, weekday=day.weekday()):
            for start, end in self._window_slots(day, window):
                if start <= now:  # horário já passou
                    continue
                if any(start < busy_end and end > busy_start for busy_start, busy_end in taken):
                    continue
                slots.append({"start_at": start, "end_at": end})
        return sorted(slots, key=lambda s: s["start_at"])

    @staticmethod
    def _window_slots(day: date, window: BarberSchedule) -> list[tuple[datetime, datetime]]:
        step = timedelta(minutes=window.slot_minutes)
        cursor = timezone.make_aware(datetime.combine(day, window.start_time))
        limit = timezone.make_aware(datetime.combine(day, window.end_time))
        out: list[tuple[datetime, datetime]] = []
        while cursor + step <= limit:
            out.append((cursor, cursor + step))
            cursor += step
        return out

    def _slot_exists(self, *, barber_id: UUID | str, start_at: datetime) -> datetime | None:
        """Devolve o fim do slot se `start_at` for um horário válido da grade."""
        day = timezone.localtime(start_at).date()
        if self.time_off.is_off(barber_id=barber_id, day=day):
            return None
        for window in self.schedules.for_weekday(barber_id=barber_id, weekday=day.weekday()):
            for start, end in self._window_slots(day, window):
                if start == start_at:
                    return end
        return None

    # ── Cota do assinante ───────────────────────────────────────────────────

    def subscriber_quota(
        self, *, customer_id: UUID | str, day: date, exclude_id: UUID | str | None = None
    ) -> dict:
        used = self.appointments.month_usage(
            customer_id=customer_id, year=day.year, month=day.month, exclude_id=exclude_id
        ).count()
        return {
            "limit": SUBSCRIBER_MONTHLY_LIMIT,
            "used": used,
            "remaining": max(0, SUBSCRIBER_MONTHLY_LIMIT - used),
        }

    def _assert_quota(
        self, *, customer_id: UUID | str, day: date, exclude_id: UUID | str | None = None
    ) -> None:
        quota = self.subscriber_quota(customer_id=customer_id, day=day, exclude_id=exclude_id)
        if quota["remaining"] <= 0:
            raise BusinessRuleError(
                f"Assinante tem direito a {SUBSCRIBER_MONTHLY_LIMIT} cortes por mês "
                f"e você já usou os {quota['used']} deste mês.",
                code="subscriber_quota_exceeded",
            )

    # ── Situação pelo relógio e janela de alteração ─────────────────────────

    @staticmethod
    def effective_status(appointment: Appointment, now: datetime | None = None) -> str:  # noqa: D401
        """Situação que a pessoa vê (RN-BB7).

        Encerrado à mão (cancelado, não compareceu, finalizado) manda. No que
        segue agendado, quem decide é o relógio: começou vira Ativo, passou do
        fim vira Finalizado — e aí o corte está consumido de vez.
        """
        if appointment.status != AppointmentStatus.SCHEDULED:
            return appointment.status
        now = now or timezone.now()
        if now >= appointment.end_at:
            return AppointmentStatus.COMPLETED
        if now >= appointment.start_at:
            return AppointmentStatus.ACTIVE
        return AppointmentStatus.SCHEDULED

    @staticmethod
    def change_deadline(appointment: Appointment) -> datetime:
        """Instante a partir do qual o horário não muda mais (RN-BB6)."""
        return appointment.start_at - timedelta(minutes=CHANGE_CUTOFF_MINUTES)

    def can_change(self, appointment: Appointment, now: datetime | None = None) -> bool:
        now = now or timezone.now()
        if self.effective_status(appointment, now) not in _CHANGEABLE_STATUSES:
            return False
        return now < self.change_deadline(appointment)

    def _assert_changeable(
        self, appointment: Appointment, verbo: str, *, enforce_cutoff: bool
    ) -> None:
        """Começou, acabou ou já foi encerrado: ninguém mexe mais — nem a gestão.

        A isenção do gestor vale só para os últimos minutos antes de começar,
        onde ele ainda precisa acertar a agenda (barbeiro faltou, por exemplo).
        Depois que o atendimento entra em curso, o caminho é "não compareceu".
        """
        if self.effective_status(appointment) not in _CHANGEABLE_STATUSES:
            raise BusinessRuleError(
                f"Este horário não pode mais ser {verbo}.", code="not_changeable"
            )
        if enforce_cutoff and timezone.now() >= self.change_deadline(appointment):
            raise BusinessRuleError(
                f"Só dá para {'remarcar' if verbo == 'remarcado' else 'cancelar'} até "
                f"{CHANGE_CUTOFF_MINUTES} minutos antes da hora marcada.",
                code="too_late_to_change",
            )

    # ── Pagamento do corte avulso (RN-BB8) ──────────────────────────────────

    def release_unpaid(self) -> int:
        """Vence os Pix no prazo estourado e devolve os horários à lista.

        Roda antes de listar horários livres e antes de marcar: assim o
        horário volta a ficar disponível sem depender de tarefa agendada.
        """
        liberados = 0
        for payment in self.payments.expire_overdue():
            liberados += self._apply_payment_to_appointments(payment)
        return liberados

    def settle_appointment_for(self, payment: Payment) -> int:
        """Reflete a situação da cobrança nos agendamentos que dependem dela."""
        with use_tenant(payment.tenant_id):
            return self._apply_payment_to_appointments(payment)

    @transaction.atomic
    def _apply_payment_to_appointments(self, payment: Payment) -> int:
        pendentes = self.appointments.query().filter(
            payment_id=payment.pk, status=AppointmentStatus.AWAITING_PAYMENT
        )
        if payment.status == PaymentStatus.APPROVED:
            novo, acao = AppointmentStatus.SCHEDULED, "appointment.paid"
        elif payment.status in _FAILED_PAYMENT_STATUSES:
            novo, acao = AppointmentStatus.CANCELLED, "appointment.payment_expired"
        else:
            return 0

        afetados = 0
        for appointment in pendentes:
            appointment.status = novo
            appointment.save(update_fields=["status", "updated_at"])
            audit.record(
                action=acao,
                entity_type="Appointment",
                entity_id=appointment.id,
                actor_id=appointment.customer_id,
                diff={"payment": str(payment.pk), "payment_status": payment.status},
            )
            afetados += 1
        return afetados

    def refresh_payment(self, appointment: Appointment) -> Appointment:
        """Consulta o provedor e aplica o resultado — usado pela tela do QR."""
        if appointment.payment_id is None:
            return appointment
        payment = self.payments.sync(appointment.payment)
        self._apply_payment_to_appointments(payment)
        appointment.refresh_from_db()
        return appointment

    # ── Agendar, remarcar, cancelar ─────────────────────────────────────────

    def _assert_no_overlap(
        self,
        *,
        barber_id: UUID | str,
        start_at: datetime,
        end_at: datetime,
        exclude_id: UUID | str | None = None,
    ) -> None:
        if self.appointments.overlapping(
            barber_id=barber_id, start_at=start_at, end_at=end_at, exclude_id=exclude_id
        ).exists():
            raise ConflictError(
                "Esse horário acabou de ser preenchido. Escolha outro.",
                code="appointment_overlap",
            )

    @staticmethod
    def _price_for(is_subscriber: bool) -> Decimal:
        return Decimal("0.00") if is_subscriber else walk_in_price()

    @staticmethod
    def _customer(customer_id: UUID | str) -> User:
        return User.objects.get(pk=customer_id)

    @transaction.atomic
    def book(
        self,
        *,
        barber_id: UUID | str,
        customer_id: UUID | str,
        start_at: datetime,
        notes: str = "",
        actor_id: UUID | str | None = None,
    ) -> Appointment:
        barber = self.barbers.get(barber_id)
        if not barber.is_active:
            raise BusinessRuleError(
                "Este barbeiro não está atendendo no momento.", code="barber_inactive"
            )
        if start_at <= timezone.now():  # RN-BB3
            raise BusinessRuleError(
                "Não é possível marcar em um horário que já passou.", code="start_in_past"
            )

        is_subscriber = self._is_subscriber(customer_id)
        end_at = self._slot_exists(barber_id=barber.id, start_at=start_at)  # RN-BB2
        if end_at is None:
            raise BusinessRuleError(
                "Este barbeiro não atende nesse horário.", code="slot_not_offered"
            )

        day = timezone.localtime(start_at).date()
        if is_subscriber:  # RN-BB4
            self._assert_quota(customer_id=customer_id, day=day)

        # Horários com Pix vencido voltam para a lista antes de conferir a colisão.
        self.release_unpaid()
        self._assert_no_overlap(barber_id=barber.id, start_at=start_at, end_at=end_at)  # RN-BB1

        preco = self._price_for(is_subscriber)  # RN-BB5
        payment = None
        com_credito = False
        situacao = AppointmentStatus.SCHEDULED
        if not is_subscriber:
            # RN-BB9: crédito de um horário desistido paga o próximo, sem Pix.
            if self.credits.has_enough(user_id=customer_id, amount=preco):
                self.credits.spend(
                    user_id=customer_id,
                    amount=preco,
                    note=f"{barber} {timezone.localtime(start_at):%d/%m %H:%M}",
                    actor_id=actor_id,
                )
                com_credito = True
            else:  # RN-BB8: sem crédito, só libera depois que o Pix cair
                payment = self.payments.open_pix_charge(
                    amount=preco,
                    description=(
                        f"Corte de cabelo — {barber} "
                        f"{timezone.localtime(start_at):%d/%m %H:%M}"
                    ),
                    payer=self._customer(customer_id),
                )
                situacao = AppointmentStatus.AWAITING_PAYMENT

        appointment = self.appointments.create(
            barber_id=barber.id,
            customer_id=customer_id,
            start_at=start_at,
            end_at=end_at,
            is_subscriber=is_subscriber,
            price=preco,
            payment=payment,
            paid_with_credit=com_credito,
            status=situacao,
            notes=notes,
            created_by_id=actor_id or customer_id,
        )
        audit.record(
            action="appointment.booked",
            entity_type="Appointment",
            entity_id=appointment.id,
            actor_id=actor_id or customer_id,
            diff={"barber": str(barber), "start_at": start_at.isoformat()},
        )
        return appointment

    @transaction.atomic
    def reschedule(
        self,
        *,
        appointment_id: UUID | str,
        start_at: datetime,
        actor_id: UUID | str,
        barber_id: UUID | str | None = None,
        enforce_cutoff: bool = True,
    ) -> Appointment:
        appointment = self.appointments.get(appointment_id)
        self._assert_changeable(appointment, "remarcado", enforce_cutoff=enforce_cutoff)  # RN-BB6
        if start_at <= timezone.now():
            raise BusinessRuleError(
                "Não é possível marcar em um horário que já passou.", code="start_in_past"
            )

        target_barber = barber_id or appointment.barber_id
        end_at = self._slot_exists(barber_id=target_barber, start_at=start_at)
        if end_at is None:
            raise BusinessRuleError(
                "Este barbeiro não atende nesse horário.", code="slot_not_offered"
            )

        # Mudar de mês revalida a cota; o próprio agendamento não conta contra ele.
        if appointment.is_subscriber:
            self._assert_quota(
                customer_id=appointment.customer_id,
                day=timezone.localtime(start_at).date(),
                exclude_id=appointment.id,
            )

        self._assert_no_overlap(
            barber_id=target_barber,
            start_at=start_at,
            end_at=end_at,
            exclude_id=appointment.id,
        )

        previous = appointment.start_at
        appointment.barber_id = target_barber
        appointment.start_at = start_at
        appointment.end_at = end_at
        appointment.save(update_fields=["barber", "start_at", "end_at", "updated_at"])
        audit.record(
            action="appointment.rescheduled",
            entity_type="Appointment",
            entity_id=appointment.id,
            actor_id=actor_id,
            diff={"de": previous.isoformat(), "para": start_at.isoformat()},
        )
        return appointment

    @transaction.atomic
    def cancel(
        self,
        *,
        appointment_id: UUID | str,
        actor_id: UUID | str,
        enforce_cutoff: bool = True,
    ) -> Appointment:
        appointment = self.appointments.get(appointment_id)
        self._assert_changeable(appointment, "cancelado", enforce_cutoff=enforce_cutoff)  # RN-BB6
        self._release_value(appointment, actor_id)
        appointment.status = AppointmentStatus.CANCELLED
        appointment.save(update_fields=["status", "updated_at"])
        audit.record(
            action="appointment.cancelled",
            entity_type="Appointment",
            entity_id=appointment.id,
            actor_id=actor_id,
        )
        return appointment

    def _release_value(self, appointment: Appointment, actor_id: UUID | str) -> None:
        """Devolve o valor do horário desistido (RN-BB9).

        Pago em dinheiro vira crédito no perfil — o grêmio não devolve por Pix,
        mas também não fica com valor de corte que não vai acontecer. Pago com
        crédito, o crédito volta. Ainda aguardando Pix, a cobrança é fechada
        para ninguém pagar um horário que deixou de existir.
        """
        quando = timezone.localtime(appointment.start_at).strftime("%d/%m %H:%M")
        if appointment.paid_with_credit:
            self.credits.add(
                user_id=appointment.customer_id,
                amount=appointment.price,
                reason=CreditReason.APPOINTMENT_CANCELLED,
                note=f"Horário de {quando} cancelado",
                actor_id=actor_id,
            )
            return

        if appointment.payment_id is None:
            return  # assinante: não há valor envolvido

        payment = appointment.payment
        if payment.status == PaymentStatus.APPROVED:
            self.credits.add(
                user_id=appointment.customer_id,
                amount=payment.amount,
                reason=CreditReason.APPOINTMENT_CANCELLED,
                payment=payment,
                note=f"Horário de {quando} cancelado",
                actor_id=actor_id,
            )
        else:
            self.payments.cancel(payment, actor_id=actor_id)

    @transaction.atomic
    def finish(
        self, *, appointment_id: UUID | str, actor_id: UUID | str, no_show: bool = False
    ) -> Appointment:
        appointment = self.appointments.get(appointment_id)
        if appointment.status != AppointmentStatus.SCHEDULED:
            raise BusinessRuleError(
                "Este horário já foi encerrado.", code="not_finishable"
            )
        appointment.status = (
            AppointmentStatus.NO_SHOW if no_show else AppointmentStatus.COMPLETED
        )
        appointment.save(update_fields=["status", "updated_at"])
        audit.record(
            action="appointment.no_show" if no_show else "appointment.completed",
            entity_type="Appointment",
            entity_id=appointment.id,
            actor_id=actor_id,
        )
        return appointment

    def avulso_report(self, *, year: int) -> list[dict]:
        """Receita de corte avulso por mês (ano civil) — só Pix pago de
        verdade. Assinante nunca paga (RN-BB4), e corte pago com o próprio
        crédito não entra de novo: esse dinheiro já foi contado quando o
        crédito foi gerado (RN-BB9), contar aqui seria contar duas vezes.

        Agrupado por Payment.paid_at (quando o Pix caiu), não pelo horário
        do corte — é o análogo, do lado da barbearia, do "arrecadado" que
        o Financeiro já mostra pras mensalidades.
        """
        report = []
        for month in range(1, 13):
            period = date(year, month, 1)
            last_day = date(year, month, monthrange(year, month)[1])
            qs = self.appointments.query().filter(
                is_subscriber=False,
                paid_with_credit=False,
                payment__status=PaymentStatus.APPROVED,
                payment__paid_at__date__gte=period,
                payment__paid_at__date__lte=last_day,
            )
            report.append(
                {
                    "period": period,
                    "revenue": qs.aggregate(s=Sum("price"))["s"] or Decimal("0.00"),
                    "count": qs.count(),
                }
            )
        return report

    # ── Agenda pública (RN-BB12) ─────────────────────────────────────────────

    def get_or_create_public_agenda_link(self, *, actor_id: str) -> PublicAgendaLink:
        """Um link por organização — reaproveita o ativo se já existir."""
        existing = self.public_agenda_links.active().first()
        if existing is not None:
            return existing
        link = self.public_agenda_links.create()
        audit.record(
            action="barbershop.public_agenda_link_created",
            entity_type="PublicAgendaLink",
            entity_id=link.id,
            actor_id=actor_id,
        )
        return link

    @transaction.atomic
    def regenerate_public_agenda_link(self, *, actor_id: str) -> PublicAgendaLink:
        """Revoga o link atual e gera um novo — quem tinha o link antigo
        perde o acesso na hora."""
        self.public_agenda_links.active().update(is_active=False)
        link = self.public_agenda_links.create()
        audit.record(
            action="barbershop.public_agenda_link_regenerated",
            entity_type="PublicAgendaLink",
            entity_id=link.id,
            actor_id=actor_id,
        )
        return link

    @staticmethod
    def today_agenda_by_token(*, token: str) -> dict | None:
        """Agenda pública do dia — sem login, o tenant vem do token, nunca
        de sessão. `None` se o token não existe ou foi revogado; o token é
        globalmente único, então essa é a única consulta do módulo que não
        passa por `for_current_tenant()` (não há tenant ainda pra filtrar).
        """
        link = PublicAgendaLink.objects.filter(token=token, is_active=True).first()
        if link is None:
            return None
        with use_tenant(link.tenant_id):
            today = timezone.localdate()
            appointments = (
                AppointmentRepository()
                .query()
                .filter(start_at__date=today)
                .exclude(status=AppointmentStatus.CANCELLED)
                .select_related("barber", "customer")
                .order_by("start_at")
            )
            return {"date": today, "appointments": [_public_agenda_entry(a) for a in appointments]}
