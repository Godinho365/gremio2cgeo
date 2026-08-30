"""Barbearia: grade do barbeiro, horários livres, cota do assinante, remarcar/cancelar."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import RoleCode
from apps.accounts.services import OnboardingService, UserService
from apps.barbershop.models import AppointmentStatus, Barber
from apps.barbershop.services import BarbershopService
from apps.finance.models import PlanCode, plan_price
from apps.finance.services import FinanceService
from core.context import use_tenant

pytestmark = pytest.mark.django_db


def _make_subscriber(tenant, user):
    """Dá ao usuário um BillingProfile ativo — é isso que faz o service tratar
    a pessoa como assinante na Barbearia (nunca mais um campo confiado do
    cliente)."""
    with use_tenant(tenant.id):
        if not user.posto_graduacao:
            user.posto_graduacao = "Cel"
            user.save(update_fields=["posto_graduacao"])
        FinanceService().activate_billing(
            user=user,
            plan=PlanCode.ASSOCIADO,
            started_period=timezone.localdate().replace(day=1),
        )
        # Vencimento é sempre dia 5 (travado) — se hoje já passou do dia 5,
        # a mensalidade do mês corrente nasceria vencida. Paga na hora pra
        # simular quem está genuinamente em dia, não travado a um dia do mês.
        FinanceService().register_payment(
            user=user, amount=plan_price(PlanCode.ASSOCIADO), method="pix", paid_at=timezone.now(),
        )


def _org(name: str):
    tenant, admin = OnboardingService().create_organization(
        org_name=name, admin_username=f"admin_{name}", admin_password="supersecret123"
    )
    # Pix exige e-mail do pagador; o admin de onboarding nasce sem um.
    admin.email = f"{name}@example.com"
    admin.save(update_fields=["email"])
    return tenant, admin


def _next_weekday(weekday: int) -> date:
    """Próxima ocorrência do dia da semana pedido — sempre no futuro."""
    today = timezone.localdate()
    ahead = (weekday - today.weekday()) % 7 or 7
    return today + timedelta(days=ahead)


def _at(day: date, hour: int, minute: int = 0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _barber_with_grid(tenant, actor, *, weekday: int, slot_minutes: int = 30) -> Barber:
    """Barbeiro que atende das 9h às 11h no dia pedido."""
    with use_tenant(tenant.id):
        service = BarbershopService()
        barber = service.create_barber(name="Zé da Navalha", actor_id=str(actor.pk))
        service.set_schedule(
            barber_id=barber.id,
            windows=[
                {
                    "weekday": weekday,
                    "start_time": time(9, 0),
                    "end_time": time(11, 0),
                    "slot_minutes": slot_minutes,
                }
            ],
            actor_id=str(actor.pk),
        )
    return barber


# ── Grade e horários livres ─────────────────────────────────────────────────


def test_slots_come_from_the_barbers_weekly_grid():
    tenant, admin = _org("bb1")
    day = _next_weekday(2)  # quarta
    barber = _barber_with_grid(tenant, admin, weekday=2)
    with use_tenant(tenant.id):
        slots = BarbershopService().available_slots(barber_id=barber.id, day=day)
    # 9h–11h de 30 em 30 = 4 horários.
    assert len(slots) == 4
    assert slots[0]["start_at"] == _at(day, 9, 0)
    assert slots[-1]["end_at"] == _at(day, 11, 0)


def test_no_slots_on_a_day_the_barber_does_not_work():
    tenant, admin = _org("bb2")
    barber = _barber_with_grid(tenant, admin, weekday=2)
    with use_tenant(tenant.id):
        slots = BarbershopService().available_slots(barber_id=barber.id, day=_next_weekday(4))
    assert slots == []


def test_time_off_clears_the_day():
    tenant, admin = _org("bb3")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    with use_tenant(tenant.id):
        service = BarbershopService()
        service.add_time_off(
            barber_id=barber.id, start_date=day, reason="Folga", actor_id=str(admin.pk)
        )
        assert service.available_slots(barber_id=barber.id, day=day) == []
        assert service.works_on(barber_id=barber.id, day=day) is False


def test_overlapping_windows_on_the_same_day_are_rejected():
    tenant, admin = _org("bb4")
    from core.exceptions import BusinessRuleError

    with use_tenant(tenant.id):
        service = BarbershopService()
        barber = service.create_barber(name="Tesoura", actor_id=str(admin.pk))
        with pytest.raises(BusinessRuleError, match="sobrepostos"):
            service.set_schedule(
                barber_id=barber.id,
                windows=[
                    {"weekday": 1, "start_time": time(9), "end_time": time(12),
                     "slot_minutes": 30},
                    {"weekday": 1, "start_time": time(11), "end_time": time(13),
                     "slot_minutes": 30},
                ],
                actor_id=str(admin.pk),
            )


# ── Marcar ──────────────────────────────────────────────────────────────────


def test_booking_takes_the_slot_out_of_the_list(client: APIClient):
    tenant, admin = _org("bb5")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    client.force_authenticate(admin)

    resp = client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9).isoformat()},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    # Avulso nasce aguardando o Pix, mas já segura o horário (RN-BB8).
    assert resp.data["status"] == AppointmentStatus.AWAITING_PAYMENT

    livres = client.get(f"/api/barbers/{barber.id}/horarios-livres?date={day:%Y-%m-%d}")
    assert len(livres.data) == 3


def test_two_people_cannot_take_the_same_slot(client: APIClient):
    tenant, admin = _org("bb6")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    with use_tenant(tenant.id):
        outro = UserService().create_user(
            username="cabo_silva", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
            email="cabo_silva@example.com",
        )
    body = {"barber": str(barber.id), "start_at": _at(day, 9).isoformat()}

    client.force_authenticate(admin)
    assert client.post("/api/appointments", body, format="json").status_code == 201

    client.force_authenticate(outro)
    conflito = client.post("/api/appointments", body, format="json")
    assert conflito.status_code == 409
    assert conflito.data["error"]["code"] == "appointment_overlap"


def test_cannot_book_a_time_the_barber_does_not_offer(client: APIClient):
    tenant, admin = _org("bb7")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    client.force_authenticate(admin)
    # 9h15 não é começo de slot; 14h está fora da janela.
    for hora, minuto in ((9, 15), (14, 0)):
        resp = client.post(
            "/api/appointments",
            {
                "barber": str(barber.id),
                "start_at": _at(day, hora, minuto).isoformat(),
            },
            format="json",
        )
        assert resp.status_code == 422
        assert resp.data["error"]["code"] == "slot_not_offered"


def test_cannot_book_in_the_past(client: APIClient):
    tenant, admin = _org("bb8")
    weekday = (timezone.localdate() - timedelta(days=7)).weekday()
    barber = _barber_with_grid(tenant, admin, weekday=weekday)
    client.force_authenticate(admin)
    resp = client.post(
        "/api/appointments",
        {
            "barber": str(barber.id),
            "start_at": _at(timezone.localdate() - timedelta(days=7), 9).isoformat(),
        },
        format="json",
    )
    assert resp.status_code == 422
    assert resp.data["error"]["code"] == "start_in_past"


# ── Assinante x avulso ──────────────────────────────────────────────────────


def test_walk_in_pays_and_subscriber_does_not(client: APIClient):
    tenant, admin = _org("bb9")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    assinante_user = _payer(tenant, "sd_bb9_assinante")
    _make_subscriber(tenant, assinante_user)

    client.force_authenticate(admin)
    avulso = client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9).isoformat()},
        format="json",
    )

    client.force_authenticate(assinante_user)
    assinante = client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9, 30).isoformat()},
        format="json",
    )
    assert Decimal(avulso.data["price"]) == Decimal("15.00")
    assert Decimal(assinante.data["price"]) == Decimal("0.00")


def test_subscriber_is_limited_to_four_cuts_per_month(client: APIClient):
    """Grade de 9h às 11h30 (5 slots de 30min) — precisa de um 5º horário
    válido pra isolar "cota estourada" de "horário não oferecido"."""
    tenant, admin = _org("bb10")
    day = _next_weekday(2)
    with use_tenant(tenant.id):
        service = BarbershopService()
        barber = service.create_barber(name="Zé da Navalha", actor_id=str(admin.pk))
        service.set_schedule(
            barber_id=barber.id,
            windows=[
                {"weekday": 2, "start_time": time(9, 0), "end_time": time(11, 30),
                 "slot_minutes": 30}
            ],
            actor_id=str(admin.pk),
        )
    _make_subscriber(tenant, admin)
    client.force_authenticate(admin)

    for hora, minuto in ((9, 0), (9, 30), (10, 0), (10, 30)):
        resp = client.post(
            "/api/appointments",
            {"barber": str(barber.id), "start_at": _at(day, hora, minuto).isoformat()},
            format="json",
        )
        assert resp.status_code == 201, resp.data

    cota = client.get(f"/api/appointments/cota?date={day:%Y-%m-%d}")
    assert cota.data == {"limit": 4, "used": 4, "remaining": 0}

    quinto = client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 11, 0).isoformat()},
        format="json",
    )
    assert quinto.status_code == 422
    assert quinto.data["error"]["code"] == "subscriber_quota_exceeded"


def test_cancelling_gives_the_subscriber_cut_back(client: APIClient):
    tenant, admin = _org("bb11")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    _make_subscriber(tenant, admin)
    client.force_authenticate(admin)

    marcados = []
    for hora, minuto in ((9, 0), (9, 30), (10, 0)):
        resp = client.post(
            "/api/appointments",
            {"barber": str(barber.id), "start_at": _at(day, hora, minuto).isoformat()},
            format="json",
        )
        marcados.append(resp.data["id"])

    assert client.post(f"/api/appointments/{marcados[0]}/cancelar").status_code == 200
    cota = client.get(f"/api/appointments/cota?date={day:%Y-%m-%d}")
    assert cota.data["remaining"] == 2

    de_novo = client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 10, 30).isoformat()},
        format="json",
    )
    assert de_novo.status_code == 201, de_novo.data


def test_delinquent_subscriber_does_not_get_the_free_cut(client: APIClient):
    """Vencido/inadimplente perde o corte de assinante até regularizar — o
    BillingProfile continua ativo, só a situação financeira muda."""
    from apps.finance.models import BillingProfile, FinancialStatus

    tenant, admin = _org("bb30")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    with use_tenant(tenant.id):
        cliente = UserService().create_user(
            username="sd_inadimplente", password="supersecret123",
            posto_graduacao="Cel", tenant_id=tenant.id, email="sd_inadimplente@example.com",
        )
    _make_subscriber(tenant, cliente)
    with use_tenant(tenant.id):
        perfil = BillingProfile.objects.get(user=cliente)
        perfil.financial_status = FinancialStatus.DELINQUENT
        perfil.save(update_fields=["financial_status"])

    client.force_authenticate(cliente)
    resp = client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9).isoformat()},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["is_subscriber"] is False
    assert Decimal(resp.data["price"]) == Decimal("15.00")


def test_overdue_subscriber_does_not_get_the_free_cut(client: APIClient):
    from apps.finance.models import BillingProfile, FinancialStatus

    tenant, admin = _org("bb31")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    with use_tenant(tenant.id):
        cliente = UserService().create_user(
            username="sd_vencido", password="supersecret123",
            posto_graduacao="Cel", tenant_id=tenant.id, email="sd_vencido@example.com",
        )
    _make_subscriber(tenant, cliente)
    with use_tenant(tenant.id):
        perfil = BillingProfile.objects.get(user=cliente)
        perfil.financial_status = FinancialStatus.OVERDUE
        perfil.save(update_fields=["financial_status"])

    client.force_authenticate(cliente)
    resp = client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9).isoformat()},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["is_subscriber"] is False


# ── Remarcar e cancelar ─────────────────────────────────────────────────────


def test_reschedule_moves_the_appointment_and_frees_the_old_slot(client: APIClient):
    tenant, admin = _org("bb12")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    client.force_authenticate(admin)

    marcado = client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9).isoformat()},
        format="json",
    ).data

    movido = client.post(
        f"/api/appointments/{marcado['id']}/remarcar",
        {"start_at": _at(day, 10, 30).isoformat()},
        format="json",
    )
    assert movido.status_code == 200, movido.data
    assert movido.data["start_at"].startswith(f"{day:%Y-%m-%d}")

    livres = client.get(f"/api/barbers/{barber.id}/horarios-livres?date={day:%Y-%m-%d}")
    inicios = [s["start_at"] for s in livres.data]
    assert any(i.startswith(f"{day:%Y-%m-%d}T09:00") for i in inicios)  # 9h voltou


def test_reschedule_into_a_taken_slot_conflicts(client: APIClient):
    tenant, admin = _org("bb13")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    client.force_authenticate(admin)

    primeiro = client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9).isoformat()},
        format="json",
    ).data
    client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9, 30).isoformat()},
        format="json",
    )
    conflito = client.post(
        f"/api/appointments/{primeiro['id']}/remarcar",
        {"start_at": _at(day, 9, 30).isoformat()},
        format="json",
    )
    assert conflito.status_code == 409


def test_someone_else_cannot_cancel_your_appointment(client: APIClient):
    tenant, admin = _org("bb14")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    with use_tenant(tenant.id):
        dono = UserService().create_user(
            username="sd_costa", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
            email="sd_costa@example.com",
        )
        intruso = UserService().create_user(
            username="sd_lima", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
            email="sd_lima@example.com",
        )

    client.force_authenticate(dono)
    marcado = client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9).isoformat()},
        format="json",
    ).data

    client.force_authenticate(intruso)
    assert client.post(f"/api/appointments/{marcado['id']}/cancelar").status_code == 422

    client.force_authenticate(dono)
    assert client.post(f"/api/appointments/{marcado['id']}/cancelar").status_code == 200


def test_customer_only_sees_their_own_appointments(client: APIClient):
    tenant, admin = _org("bb15")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    with use_tenant(tenant.id):
        outro = UserService().create_user(
            username="sd_reis", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
            email="sd_reis@example.com",
        )

    client.force_authenticate(admin)
    client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9).isoformat()},
        format="json",
    )
    client.force_authenticate(outro)
    client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9, 30).isoformat()},
        format="json",
    )

    minhas = client.get("/api/appointments")
    assert minhas.data["count"] == 1
    # Pedir "todos" sem ser da administração continua trazendo só as próprias.
    assert client.get("/api/appointments?scope=all").data["count"] == 1

    client.force_authenticate(admin)
    assert client.get("/api/appointments?scope=all").data["count"] == 2


# ── Cadastro do barbeiro ────────────────────────────────────────────────────


def test_only_management_registers_barbers(client: APIClient):
    tenant, admin = _org("bb16")
    with use_tenant(tenant.id):
        comum = UserService().create_user(
            username="sd_souza", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
            email="sd_souza@example.com",
        )
    client.force_authenticate(comum)
    assert client.post("/api/barbers", {"name": "X"}, format="json").status_code == 422
    # Mas todo mundo enxerga a lista para poder marcar.
    assert client.get("/api/barbers").status_code == 200

    client.force_authenticate(admin)
    assert client.post("/api/barbers", {"name": "X"}, format="json").status_code == 201


def test_barbershop_role_manages_the_module(client: APIClient):
    tenant, admin = _org("bb17")
    with use_tenant(tenant.id):
        gerente = UserService().create_user(
            username="barbeiro_chefe",
            password="supersecret123",
            role_codes=[RoleCode.BARBERSHOP],
            tenant_id=tenant.id,
        )
    client.force_authenticate(gerente)
    assert client.post("/api/barbers", {"name": "Navalha"}, format="json").status_code == 201


def test_cannot_delete_a_barber_with_appointments_ahead(client: APIClient):
    """Vale para o agendado e também para o avulso à espera do Pix."""
    tenant, admin = _org("bb18")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    client.force_authenticate(admin)
    marcado = client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9).isoformat()},
        format="json",
    ).data

    bloqueado = client.delete(f"/api/barbers/{barber.id}")
    assert bloqueado.status_code == 422
    assert bloqueado.data["error"]["code"] == "barber_has_appointments"

    client.post(f"/api/appointments/{marcado['id']}/cancelar")
    assert client.delete(f"/api/barbers/{barber.id}").status_code == 204


def test_barber_list_filters_by_working_day(client: APIClient):
    tenant, admin = _org("bb19")
    _barber_with_grid(tenant, admin, weekday=2)  # só quarta
    client.force_authenticate(admin)
    quarta = _next_weekday(2)
    sexta = _next_weekday(4)
    assert client.get(f"/api/barbers?date={quarta:%Y-%m-%d}").data["count"] == 1
    assert client.get(f"/api/barbers?date={sexta:%Y-%m-%d}").data["count"] == 0


def test_tenant_isolation_on_barbers(client: APIClient):
    tenant_a, admin_a = _org("bb20a")
    tenant_b, admin_b = _org("bb20b")
    _barber_with_grid(tenant_a, admin_a, weekday=2)
    client.force_authenticate(admin_b)
    assert client.get("/api/barbers").data["count"] == 0


def test_finishing_is_management_only(client: APIClient):
    tenant, admin = _org("bb21")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    with use_tenant(tenant.id):
        cliente = UserService().create_user(
            username="sd_alves", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
            email="sd_alves@example.com",
        )
    _make_subscriber(tenant, cliente)
    client.force_authenticate(cliente)
    marcado = client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9).isoformat()},
        format="json",
    ).data
    assert client.post(f"/api/appointments/{marcado['id']}/concluir").status_code == 422

    client.force_authenticate(admin)
    concluido = client.post(f"/api/appointments/{marcado['id']}/concluir")
    assert concluido.status_code == 200
    assert concluido.data["status"] == AppointmentStatus.COMPLETED


# ── Janela de alteração e situação pelo relógio ─────────────────────────────


def _appointment_at(tenant, *, customer, barber, start_at, is_subscriber=False):
    """Crava um agendamento direto no repositório — para poder simular o relógio."""
    from apps.barbershop.repositories import AppointmentRepository

    with use_tenant(tenant.id):
        return AppointmentRepository().create(
            barber_id=barber.id,
            customer_id=customer.pk,
            start_at=start_at,
            end_at=start_at + timedelta(minutes=30),
            is_subscriber=is_subscriber,
            price=0 if is_subscriber else Decimal("15.00"),
            status=AppointmentStatus.SCHEDULED,
        )


def test_status_follows_the_clock():
    """Agendado antes da hora, Ativo durante, Finalizado depois (RN-BB7)."""
    tenant, admin = _org("bb22")
    barber = _barber_with_grid(tenant, admin, weekday=2)
    inicio = timezone.now() + timedelta(hours=2)
    ag = _appointment_at(tenant, customer=admin, barber=barber, start_at=inicio)

    with use_tenant(tenant.id):
        s = BarbershopService()
        assert s.effective_status(ag, inicio - timedelta(minutes=1)) == AppointmentStatus.SCHEDULED
        assert s.effective_status(ag, inicio) == AppointmentStatus.ACTIVE
        assert s.effective_status(ag, inicio + timedelta(minutes=29)) == AppointmentStatus.ACTIVE
        assert s.effective_status(ag, inicio + timedelta(minutes=30)) == AppointmentStatus.COMPLETED


def test_cancelled_and_no_show_ignore_the_clock():
    """O que foi encerrado à mão não volta a ser Ativo (RN-BB7)."""
    tenant, admin = _org("bb23")
    barber = _barber_with_grid(tenant, admin, weekday=2)
    inicio = timezone.now() - timedelta(hours=1)
    for gravado in (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW):
        ag = _appointment_at(tenant, customer=admin, barber=barber, start_at=inicio)
        ag.status = gravado
        ag.save(update_fields=["status"])
        with use_tenant(tenant.id):
            assert BarbershopService().effective_status(ag) == gravado


def test_the_api_reports_the_clock_status(client: APIClient):
    tenant, admin = _org("bb24")
    barber = _barber_with_grid(tenant, admin, weekday=2)
    # Um em curso agora, outro que já terminou.
    _appointment_at(
        tenant, customer=admin, barber=barber, start_at=timezone.now() - timedelta(minutes=5)
    )
    _appointment_at(
        tenant, customer=admin, barber=barber, start_at=timezone.now() - timedelta(hours=3)
    )
    client.force_authenticate(admin)
    situacoes = {a["status"] for a in client.get("/api/appointments").data["results"]}
    assert situacoes == {AppointmentStatus.ACTIVE, AppointmentStatus.COMPLETED}


def test_customer_cannot_change_inside_the_ten_minute_window(client: APIClient):
    """Faltando menos de 10 minutos, o cliente não remarca nem cancela (RN-BB6)."""
    tenant, admin = _org("bb25")
    barber = _barber_with_grid(tenant, admin, weekday=2)
    with use_tenant(tenant.id):
        cliente = UserService().create_user(
            username="sd_pinto", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
            email="sd_pinto@example.com",
        )
    ag = _appointment_at(
        tenant, customer=cliente, barber=barber, start_at=timezone.now() + timedelta(minutes=9)
    )
    client.force_authenticate(cliente)

    cancelar = client.post(f"/api/appointments/{ag.id}/cancelar")
    assert cancelar.status_code == 422
    assert cancelar.data["error"]["code"] == "too_late_to_change"

    remarcar = client.post(
        f"/api/appointments/{ag.id}/remarcar",
        {"start_at": _at(_next_weekday(2), 9).isoformat()},
        format="json",
    )
    assert remarcar.status_code == 422
    assert remarcar.data["error"]["code"] == "too_late_to_change"


def test_customer_can_still_change_just_outside_the_window(client: APIClient):
    tenant, admin = _org("bb26")
    barber = _barber_with_grid(tenant, admin, weekday=2)
    with use_tenant(tenant.id):
        cliente = UserService().create_user(
            username="sd_gomes", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
            email="sd_gomes@example.com",
        )
    ag = _appointment_at(
        tenant, customer=cliente, barber=barber, start_at=timezone.now() + timedelta(minutes=11)
    )
    client.force_authenticate(cliente)
    assert client.post(f"/api/appointments/{ag.id}/cancelar").status_code == 200


def test_management_can_still_fix_the_agenda_at_the_last_minute(client: APIClient):
    tenant, admin = _org("bb27")
    barber = _barber_with_grid(tenant, admin, weekday=2)
    ag = _appointment_at(
        tenant, customer=admin, barber=barber, start_at=timezone.now() + timedelta(minutes=2)
    )
    client.force_authenticate(admin)
    assert client.post(f"/api/appointments/{ag.id}/cancelar").status_code == 200


def test_an_appointment_that_ran_its_course_counts_as_one_cut(client: APIClient):
    """Passou do fim, o corte está consumido e não volta para a cota (RN-BB4)."""
    tenant, admin = _org("bb28")
    barber = _barber_with_grid(tenant, admin, weekday=2)
    inicio = timezone.now() - timedelta(hours=2)
    with use_tenant(tenant.id):
        cliente = UserService().create_user(
            username="sd_matos", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
            email="sd_matos@example.com",
        )
    ag = _appointment_at(
        tenant, customer=cliente, barber=barber, start_at=inicio, is_subscriber=True
    )
    client.force_authenticate(cliente)

    cota = client.get(f"/api/appointments/cota?date={timezone.localdate():%Y-%m-%d}")
    assert cota.data == {"limit": 4, "used": 1, "remaining": 3}
    assert client.get("/api/appointments").data["results"][0]["status"] == (
        AppointmentStatus.COMPLETED
    )
    # E não dá mais para devolver esse corte cancelando — nem a gestão desfaz.
    tarde = client.post(f"/api/appointments/{ag.id}/cancelar")
    assert tarde.status_code == 422
    assert tarde.data["error"]["code"] == "not_changeable"

    client.force_authenticate(admin)
    pela_gestao = client.post(f"/api/appointments/{ag.id}/cancelar")
    assert pela_gestao.status_code == 422
    assert pela_gestao.data["error"]["code"] == "not_changeable"


def test_can_change_flag_is_exposed_to_the_client(client: APIClient):
    tenant, admin = _org("bb29")
    barber = _barber_with_grid(tenant, admin, weekday=2)
    longe = _appointment_at(
        tenant, customer=admin, barber=barber, start_at=timezone.now() + timedelta(days=1)
    )
    perto = _appointment_at(
        tenant, customer=admin, barber=barber, start_at=timezone.now() + timedelta(minutes=5)
    )
    client.force_authenticate(admin)
    por_id = {a["id"]: a for a in client.get("/api/appointments").data["results"]}
    assert por_id[str(longe.id)]["can_change"] is True
    assert por_id[str(perto.id)]["can_change"] is False


# ── Corte avulso: só libera depois de pagar (RN-BB8) ────────────────────────


def _service_with_fake_gateway():
    """Service de produção; quem está fingindo é só o HTTP (ver conftest)."""
    from .conftest import PROVIDER_STATUS

    return BarbershopService(), PROVIDER_STATUS


def _payer(tenant, username: str):
    with use_tenant(tenant.id):
        u = UserService().create_user(
            username=username, password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
            email=f"{username}@example.com",
        )
    return u


def test_walk_in_is_born_awaiting_payment_with_a_qr_code():
    tenant, admin = _org("pg1")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_pix1")
    service, _ = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        ag = service.book(
            barber_id=barber.id, customer_id=cliente.pk,
            start_at=_at(day, 9),
        )

    assert ag.status == AppointmentStatus.AWAITING_PAYMENT
    assert ag.payment is not None
    assert ag.payment.qr_code
    assert ag.payment.amount == Decimal("15.00")


def test_subscriber_does_not_generate_a_charge():
    tenant, admin = _org("pg2")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_pix2")
    _make_subscriber(tenant, cliente)
    service, provedor = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        ag = service.book(
            barber_id=barber.id, customer_id=cliente.pk,
            start_at=_at(day, 9),
        )

    assert ag.status == AppointmentStatus.SCHEDULED
    assert ag.payment is None


def test_unpaid_slot_is_held_so_nobody_else_takes_it():
    tenant, admin = _org("pg3")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    um, outro = _payer(tenant, "sd_pix3a"), _payer(tenant, "sd_pix3b")
    service, _ = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        service.book(barber_id=barber.id, customer_id=um.pk,
                     start_at=_at(day, 9))
        livres = service.available_slots(barber_id=barber.id, day=day)
        assert _at(day, 9) not in [s["start_at"] for s in livres]

        from core.exceptions import ConflictError
        with pytest.raises(ConflictError):
            service.book(barber_id=barber.id, customer_id=outro.pk,
                         start_at=_at(day, 9))


def test_paying_turns_the_appointment_into_scheduled():
    tenant, admin = _org("pg4")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_pix4")
    service, provedor = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        ag = service.book(barber_id=barber.id, customer_id=cliente.pk,
                          start_at=_at(day, 9))
        provedor["value"] = "approved"
        atualizado = service.refresh_payment(ag)

    assert atualizado.status == AppointmentStatus.SCHEDULED
    assert atualizado.payment.status == "approved"


def test_an_expired_pix_frees_the_slot():
    """Não pagou no prazo: o agendamento cai e o horário volta para a lista."""
    tenant, admin = _org("pg5")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_pix5")
    service, _ = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        ag = service.book(barber_id=barber.id, customer_id=cliente.pk,
                          start_at=_at(day, 9))
        ag.payment.expires_at = timezone.now() - timedelta(minutes=1)
        ag.payment.save(update_fields=["expires_at"])

        service.release_unpaid()
        ag.refresh_from_db()
        assert ag.status == AppointmentStatus.CANCELLED

        livres = service.available_slots(barber_id=barber.id, day=day)
        assert _at(day, 9) in [s["start_at"] for s in livres]


def test_someone_else_can_book_the_slot_after_the_pix_expires():
    tenant, admin = _org("pg6")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    um, outro = _payer(tenant, "sd_pix6a"), _payer(tenant, "sd_pix6b")
    service, _ = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        primeiro = service.book(barber_id=barber.id, customer_id=um.pk,
                                start_at=_at(day, 9))
        primeiro.payment.expires_at = timezone.now() - timedelta(minutes=1)
        primeiro.payment.save(update_fields=["expires_at"])

        segundo = service.book(barber_id=barber.id, customer_id=outro.pk,
                               start_at=_at(day, 9))

    assert segundo.status == AppointmentStatus.AWAITING_PAYMENT
    primeiro.refresh_from_db()
    assert primeiro.status == AppointmentStatus.CANCELLED


def test_an_unpaid_appointment_can_be_cancelled_by_its_owner(client: APIClient):
    tenant, admin = _org("pg7")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_pix7")
    service, _ = _service_with_fake_gateway()
    with use_tenant(tenant.id):
        ag = service.book(barber_id=barber.id, customer_id=cliente.pk,
                          start_at=_at(day, 9))

    client.force_authenticate(cliente)
    assert client.post(f"/api/appointments/{ag.id}/cancelar").status_code == 200


def test_the_api_hands_the_qr_code_to_the_screen(client: APIClient):
    """O agendamento devolvido pela API carrega o Pix pronto para pagar."""
    tenant, admin = _org("pg8")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_pix8")

    client.force_authenticate(cliente)
    resp = client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9).isoformat()},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["status"] == AppointmentStatus.AWAITING_PAYMENT
    assert resp.data["payment"]["qr_code"]
    assert resp.data["payment"]["status"] == "pending"
    assert Decimal(resp.data["payment"]["amount"]) == Decimal("15.00")


@pytest.mark.no_pix
def test_booking_fails_clearly_when_pix_is_not_configured(client: APIClient):
    """Sem token do Mercado Pago, o avulso é recusado com mensagem legível."""
    tenant, admin = _org("pg9")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_pix9")

    client.force_authenticate(cliente)
    resp = client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9).isoformat()},
        format="json",
    )
    assert resp.status_code == 422
    assert resp.data["error"]["code"] == "payments_not_configured"


def test_giving_up_the_slot_also_closes_the_pix_charge():
    """RN-BB8: cancelar o horário fecha a cobrança — ninguém paga por nada."""
    tenant, admin = _org("pg10")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_pix10")
    service, _ = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        ag = service.book(barber_id=barber.id, customer_id=cliente.pk,
                          start_at=_at(day, 9))
        service.cancel(appointment_id=ag.id, actor_id=str(cliente.pk))
        ag.refresh_from_db()
        ag.payment.refresh_from_db()

    assert ag.status == AppointmentStatus.CANCELLED
    assert ag.payment.status == "cancelled"


def test_walk_in_price_comes_from_the_setting(settings):
    """Trocar WALK_IN_PRICE no .env muda a cobrança sem tocar em código."""
    tenant, admin = _org("pg11")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_pix11")
    service, _ = _service_with_fake_gateway()

    settings.WALK_IN_PRICE = "1.00"
    with use_tenant(tenant.id):
        barato = service.book(barber_id=barber.id, customer_id=cliente.pk,
                              start_at=_at(day, 9))
    assert barato.price == Decimal("1.00")
    assert barato.payment.amount == Decimal("1.00")

    settings.WALK_IN_PRICE = "15.00"
    with use_tenant(tenant.id):
        cheio = service.book(barber_id=barber.id, customer_id=cliente.pk,
                             start_at=_at(day, 9, 30))
    assert cheio.price == Decimal("15.00")

    # O que já foi marcado mantém o preço do momento da marcação.
    barato.refresh_from_db()
    assert barato.price == Decimal("1.00")


def test_the_screen_gets_the_price_from_the_server(client: APIClient, settings):
    tenant, admin = _org("pg12")
    settings.WALK_IN_PRICE = "1.00"
    client.force_authenticate(admin)
    cfg = client.get("/api/payments/config")
    assert cfg.status_code == 200
    assert cfg.data["walk_in_price"] == "1.00"
    assert cfg.data["pix_enabled"] is True


# ── Crédito do usuário (RN-BB9) ─────────────────────────────────────────────


def _saldo(tenant, user) -> Decimal:
    from apps.payments.credits import CreditService

    with use_tenant(tenant.id):
        return CreditService().balance(user.pk)


def _marca_e_paga(service, provedor, barber, cliente, quando):
    ag = service.book(barber_id=barber.id, customer_id=cliente.pk,
                      start_at=quando)
    provedor["value"] = "approved"
    ag = service.refresh_payment(ag)
    provedor["value"] = "pending"
    return ag


def test_cancelling_a_paid_appointment_turns_into_credit():
    """O dinheiro não é estornado: fica como crédito no perfil."""
    tenant, admin = _org("cr1")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_cred1")
    service, provedor = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        ag = _marca_e_paga(service, provedor, barber, cliente, _at(day, 9))
        assert ag.status == AppointmentStatus.SCHEDULED
        service.cancel(appointment_id=ag.id, actor_id=str(cliente.pk))
        ag.refresh_from_db()

    assert ag.status == AppointmentStatus.CANCELLED
    # A cobrança segue paga — o dinheiro ficou; o que muda é o crédito.
    assert ag.payment.status == "approved"
    assert _saldo(tenant, cliente) == Decimal("15.00")


def test_credit_pays_the_next_haircut_without_pix():
    tenant, admin = _org("cr2")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_cred2")
    service, provedor = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        primeiro = _marca_e_paga(service, provedor, barber, cliente, _at(day, 9))
        service.cancel(appointment_id=primeiro.id, actor_id=str(cliente.pk))

        segundo = service.book(barber_id=barber.id, customer_id=cliente.pk,
                               start_at=_at(day, 9, 30))

    # Já nasce confirmado: não passou pelo Pix.
    assert segundo.status == AppointmentStatus.SCHEDULED
    assert segundo.paid_with_credit is True
    assert segundo.payment is None
    assert _saldo(tenant, cliente) == Decimal("0.00")


def test_cancelling_a_credit_paid_appointment_gives_the_credit_back():
    tenant, admin = _org("cr3")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_cred3")
    service, provedor = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        primeiro = _marca_e_paga(service, provedor, barber, cliente, _at(day, 9))
        service.cancel(appointment_id=primeiro.id, actor_id=str(cliente.pk))
        segundo = service.book(barber_id=barber.id, customer_id=cliente.pk,
                               start_at=_at(day, 9, 30))
        assert _saldo(tenant, cliente) == Decimal("0.00")

        service.cancel(appointment_id=segundo.id, actor_id=str(cliente.pk))

    assert _saldo(tenant, cliente) == Decimal("15.00")


def test_credit_is_not_spent_twice_on_the_same_balance():
    """Saldo para um corte não pode virar dois."""
    tenant, admin = _org("cr4")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_cred4")
    service, provedor = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        pago = _marca_e_paga(service, provedor, barber, cliente, _at(day, 9))
        service.cancel(appointment_id=pago.id, actor_id=str(cliente.pk))
        assert _saldo(tenant, cliente) == Decimal("15.00")

        com_credito = service.book(barber_id=barber.id, customer_id=cliente.pk,
                                   start_at=_at(day, 9, 30))
        assert com_credito.paid_with_credit is True

        # Sem saldo, o próximo volta a exigir Pix.
        terceiro = service.book(barber_id=barber.id, customer_id=cliente.pk,
                                start_at=_at(day, 10))

    assert terceiro.paid_with_credit is False
    assert terceiro.status == AppointmentStatus.AWAITING_PAYMENT
    assert terceiro.payment is not None
    assert _saldo(tenant, cliente) == Decimal("0.00")


def test_an_unpaid_pix_never_becomes_credit():
    """Só vira crédito o que foi realmente pago."""
    tenant, admin = _org("cr5")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_cred5")
    service, _ = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        ag = service.book(barber_id=barber.id, customer_id=cliente.pk,
                          start_at=_at(day, 9))
        service.cancel(appointment_id=ag.id, actor_id=str(cliente.pk))

    assert _saldo(tenant, cliente) == Decimal("0.00")


def test_subscriber_cancellation_creates_no_credit():
    tenant, admin = _org("cr6")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_cred6")
    _make_subscriber(tenant, cliente)
    service, _ = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        ag = service.book(barber_id=barber.id, customer_id=cliente.pk,
                          start_at=_at(day, 9))
        service.cancel(appointment_id=ag.id, actor_id=str(cliente.pk))

    assert _saldo(tenant, cliente) == Decimal("0.00")


def test_the_statement_shows_where_the_credit_came_from(client: APIClient):
    tenant, admin = _org("cr7")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_cred7")
    service, provedor = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        ag = _marca_e_paga(service, provedor, barber, cliente, _at(day, 9))
        service.cancel(appointment_id=ag.id, actor_id=str(cliente.pk))
        service.book(barber_id=barber.id, customer_id=cliente.pk,
                     start_at=_at(day, 9, 30))

    client.force_authenticate(cliente)
    extrato = client.get("/api/credits")
    assert extrato.status_code == 200
    assert Decimal(extrato.data["balance"]) == Decimal("0.00")
    linhas = extrato.data["entries"]
    assert len(linhas) == 2
    assert {e["reason"] for e in linhas} == {"appointment_cancelled", "used_in_appointment"}
    # Cada linha diz de qual horário veio.
    assert all(e["note"] for e in linhas)


# ── Folga por período e replicação da grade (RN-BB10, RN-BB11) ──────────────


def test_time_off_can_cover_a_range_of_days():
    tenant, admin = _org("fo1")
    barber = _barber_with_grid(tenant, admin, weekday=2)
    primeira = _next_weekday(2)
    seguinte = primeira + timedelta(days=7)

    with use_tenant(tenant.id):
        s = BarbershopService()
        folga = s.add_time_off(
            barber_id=barber.id, start_date=primeira, end_date=seguinte,
            reason="Férias", actor_id=str(admin.pk),
        )
        assert folga.days == 8
        # As duas quartas dentro do período ficam sem horário.
        assert s.available_slots(barber_id=barber.id, day=primeira) == []
        assert s.available_slots(barber_id=barber.id, day=seguinte) == []
        # A quarta seguinte ao fim do período volta ao normal.
        assert s.available_slots(barber_id=barber.id, day=seguinte + timedelta(days=7))


def test_a_single_day_is_a_range_of_one():
    tenant, admin = _org("fo2")
    barber = _barber_with_grid(tenant, admin, weekday=2)
    day = _next_weekday(2)
    with use_tenant(tenant.id):
        folga = BarbershopService().add_time_off(
            barber_id=barber.id, start_date=day, actor_id=str(admin.pk)
        )
    assert folga.start_date == folga.end_date == day
    assert folga.days == 1


def test_overlapping_time_off_is_rejected():
    tenant, admin = _org("fo3")
    barber = _barber_with_grid(tenant, admin, weekday=2)
    inicio = _next_weekday(2)
    with use_tenant(tenant.id):
        s = BarbershopService()
        s.add_time_off(barber_id=barber.id, start_date=inicio,
                       end_date=inicio + timedelta(days=5), actor_id=str(admin.pk))
        from core.exceptions import BusinessRuleError
        with pytest.raises(BusinessRuleError, match="Já existe folga"):
            s.add_time_off(barber_id=barber.id, start_date=inicio + timedelta(days=3),
                           end_date=inicio + timedelta(days=8), actor_id=str(admin.pk))


def test_time_off_range_must_end_after_it_starts():
    tenant, admin = _org("fo4")
    barber = _barber_with_grid(tenant, admin, weekday=2)
    day = _next_weekday(2)
    from core.exceptions import BusinessRuleError

    with use_tenant(tenant.id), pytest.raises(BusinessRuleError, match="antes do primeiro"):
        BarbershopService().add_time_off(
            barber_id=barber.id, start_date=day, end_date=day - timedelta(days=1),
            actor_id=str(admin.pk),
        )


def test_removing_a_range_frees_every_day_in_it(client: APIClient):
    tenant, admin = _org("fo5")
    barber = _barber_with_grid(tenant, admin, weekday=2)
    inicio = _next_weekday(2)
    client.force_authenticate(admin)

    criada = client.post(
        f"/api/barbers/{barber.id}/folgas",
        {"start_date": f"{inicio:%Y-%m-%d}", "end_date": f"{inicio + timedelta(days=7):%Y-%m-%d}",
         "reason": "Férias"},
        format="json",
    )
    assert criada.status_code == 201, criada.data
    assert criada.data["days"] == 8
    assert client.get(f"/api/barbers/{barber.id}/horarios-livres?date={inicio:%Y-%m-%d}").data == []

    apagada = client.delete(f"/api/barbers/{barber.id}/folgas/{criada.data['id']}")
    assert apagada.status_code == 204
    assert client.get(f"/api/barbers/{barber.id}/horarios-livres?date={inicio:%Y-%m-%d}").data


def test_schedule_replicates_to_other_barbers(client: APIClient):
    tenant, admin = _org("rp1")
    origem = _barber_with_grid(tenant, admin, weekday=2)
    with use_tenant(tenant.id):
        s = BarbershopService()
        a = s.create_barber(name="Sem grade A", actor_id=str(admin.pk))
        b = s.create_barber(name="Sem grade B", actor_id=str(admin.pk))
        assert s.schedules.for_barber(a.id).count() == 0

    client.force_authenticate(admin)
    resp = client.post(
        f"/api/barbers/{origem.id}/horarios/replicar",
        {"targets": [str(a.id), str(b.id)]}, format="json",
    )
    assert resp.status_code == 200, resp.data
    assert resp.data["updated"] == 2

    with use_tenant(tenant.id):
        s = BarbershopService()
        for destino in (a, b):
            janelas = list(s.schedules.for_barber(destino.id))
            assert len(janelas) == 1
            assert janelas[0].weekday == 2
            assert janelas[0].start_time == time(9, 0)
            assert janelas[0].slot_minutes == 30
        # E os destinos passam a oferecer horário de verdade.
        assert s.available_slots(barber_id=a.id, day=_next_weekday(2))


def test_replicating_replaces_the_target_grid(client: APIClient):
    """Quem recebe fica igual à origem, não com as duas grades somadas."""
    tenant, admin = _org("rp2")
    origem = _barber_with_grid(tenant, admin, weekday=2)
    destino = _barber_with_grid(tenant, admin, weekday=4)

    client.force_authenticate(admin)
    client.post(f"/api/barbers/{origem.id}/horarios/replicar",
                {"targets": [str(destino.id)]}, format="json")

    with use_tenant(tenant.id):
        janelas = list(BarbershopService().schedules.for_barber(destino.id))
    assert [j.weekday for j in janelas] == [2]


def test_replicating_an_empty_schedule_is_refused(client: APIClient):
    tenant, admin = _org("rp3")
    with use_tenant(tenant.id):
        vazio = BarbershopService().create_barber(name="Sem grade", actor_id=str(admin.pk))
        destino = BarbershopService().create_barber(name="Destino", actor_id=str(admin.pk))
    client.force_authenticate(admin)
    resp = client.post(f"/api/barbers/{vazio.id}/horarios/replicar",
                       {"targets": [str(destino.id)]}, format="json")
    assert resp.status_code == 422
    assert resp.data["error"]["code"] == "empty_schedule"


def test_only_management_replicates_schedules(client: APIClient):
    tenant, admin = _org("rp4")
    origem = _barber_with_grid(tenant, admin, weekday=2)
    with use_tenant(tenant.id):
        destino = BarbershopService().create_barber(name="Destino", actor_id=str(admin.pk))
        comum = UserService().create_user(
            username="sd_rep", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id, email="sd_rep@example.com",
        )
    client.force_authenticate(comum)
    resp = client.post(f"/api/barbers/{origem.id}/horarios/replicar",
                       {"targets": [str(destino.id)]}, format="json")
    assert resp.status_code == 422
    assert resp.data["error"]["code"] == "forbidden"


def test_a_removed_time_off_disappears_from_the_barber(client: APIClient):
    """Exclusão aqui é lógica; o que foi apagado não pode continuar na tela."""
    tenant, admin = _org("fo6")
    barber = _barber_with_grid(tenant, admin, weekday=2)
    day = _next_weekday(2)
    client.force_authenticate(admin)

    folga = client.post(
        f"/api/barbers/{barber.id}/folgas", {"start_date": f"{day:%Y-%m-%d}"}, format="json"
    ).data
    listado = client.get(f"/api/barbers/{barber.id}").data
    assert len(listado["time_off"]) == 1

    client.delete(f"/api/barbers/{barber.id}/folgas/{folga['id']}")
    depois = client.get(f"/api/barbers/{barber.id}").data
    assert depois["time_off"] == []
    # E o dia volta a ter horário.
    assert client.get(f"/api/barbers/{barber.id}/horarios-livres?date={day:%Y-%m-%d}").data


def test_barbershop_client_can_still_book_a_haircut(client: APIClient):
    tenant, admin = _org("bb9")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    with use_tenant(tenant.id):
        cliente = UserService().create_user(
            username="cliente_bb9", password="supersecret123",
            role_codes=[RoleCode.BARBERSHOP_CLIENT], tenant_id=tenant.id,
            email="cliente_bb9@example.com",
        )
    client.force_authenticate(cliente)
    resp = client.post(
        "/api/appointments",
        {"barber": str(barber.id), "start_at": _at(day, 9).isoformat()},
        format="json",
    )
    assert resp.status_code == 201, resp.data


# ── Receita de corte avulso (comparativo mensal do Financeiro) ──────────────


def test_avulso_report_counts_paid_walkin_in_the_right_month():
    """Agrupa por Payment.paid_at (quando o Pix caiu), não pelo horário do
    corte — pode reservar num dia futuro e a cobrança ainda assim contar
    pro mês certo do relatório."""
    tenant, admin = _org("av1")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_avulso1")
    service, provedor = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        ag = _marca_e_paga(service, provedor, barber, cliente, _at(day, 9))
        assert ag.payment.status == "approved"
        ag.payment.paid_at = timezone.make_aware(datetime(2026, 3, 15, 10, 0))
        ag.payment.save(update_fields=["paid_at"])

        report = BarbershopService().avulso_report(year=2026)

    marco = report[2]
    assert marco["period"] == date(2026, 3, 1)
    assert marco["revenue"] == Decimal("15.00")
    assert marco["count"] == 1
    outros_meses = [r for i, r in enumerate(report) if i != 2]
    assert all(r["revenue"] == Decimal("0.00") and r["count"] == 0 for r in outros_meses)


def test_avulso_report_ignores_credit_paid_appointments():
    """Corte pago com o próprio crédito não conta de novo — o dinheiro já
    foi contado quando o Pix que gerou aquele crédito foi pago."""
    tenant, admin = _org("av2")
    day = _next_weekday(2)
    barber = _barber_with_grid(tenant, admin, weekday=2)
    cliente = _payer(tenant, "sd_avulso2")
    service, provedor = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        primeiro = _marca_e_paga(service, provedor, barber, cliente, _at(day, 9))
        ano = timezone.localdate().year
        primeiro.payment.paid_at = timezone.now()
        primeiro.payment.save(update_fields=["paid_at"])
        service.cancel(appointment_id=primeiro.id, actor_id=str(cliente.pk))

        segundo = service.book(
            barber_id=barber.id, customer_id=cliente.pk, start_at=_at(day, 9, 30)
        )
        assert segundo.paid_with_credit is True

        report = BarbershopService().avulso_report(year=ano)

    mes_atual = report[timezone.localdate().month - 1]
    # Só o primeiro corte (Pix de verdade) conta — o segundo, pago com
    # crédito, não gera Payment novo.
    assert mes_atual["count"] == 1
    assert mes_atual["revenue"] == Decimal("15.00")


# ── Agenda pública (sem login) ───────────────────────────────────────────────


def _marca_e_paga_hoje(service, provedor, barber, cliente, day):
    """Marcar exige horário futuro (RN-BB3) — marca daqui a uma semana
    (mesmo dia da semana da grade) e realoca pra hoje, só pra testar o
    filtro "agenda de hoje" sem depender de que horário é agora."""
    ag = _marca_e_paga(service, provedor, barber, cliente, _at(_next_weekday(day.weekday()), 9))
    duracao = ag.end_at - ag.start_at
    novo_inicio = timezone.make_aware(datetime.combine(day, time(9, 0)))
    ag.start_at = novo_inicio
    ag.end_at = novo_inicio + duracao
    ag.save(update_fields=["start_at", "end_at"])
    return ag


def test_public_agenda_link_requires_manager(client: APIClient):
    tenant, admin = _org("pub1")
    with use_tenant(tenant.id):
        comum = UserService().create_user(
            username="comum_pub1", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(comum)
    assert client.post("/api/barbershop/agenda-publica").status_code == 422

    client.force_authenticate(admin)
    resp = client.post("/api/barbershop/agenda-publica")
    assert resp.status_code == 200, resp.data
    assert resp.data["token"]


def test_public_agenda_link_is_reused_not_recreated(client: APIClient):
    tenant, admin = _org("pub2")
    client.force_authenticate(admin)
    primeiro = client.post("/api/barbershop/agenda-publica").data["token"]
    segundo = client.post("/api/barbershop/agenda-publica").data["token"]
    assert primeiro == segundo


def test_regenerating_public_agenda_link_revokes_the_old_one(client: APIClient):
    tenant, admin = _org("pub3")
    client.force_authenticate(admin)
    antigo = client.post("/api/barbershop/agenda-publica").data["token"]
    novo = client.patch("/api/barbershop/agenda-publica").data["token"]

    assert novo != antigo
    assert client.get(f"/api/barbershop/agenda-publica/{antigo}").status_code == 422
    assert client.get(f"/api/barbershop/agenda-publica/{novo}").status_code == 200


def test_public_agenda_view_shows_todays_appointments_without_login():
    """Sem force_authenticate de propósito — é exatamente o que um barbeiro
    sem conta no sistema faria: abrir o link puro."""
    tenant, admin = _org("pub4")
    day = timezone.localdate()
    barber = _barber_with_grid(tenant, admin, weekday=day.weekday())
    cliente = _payer(tenant, "sd_pub4")
    service, provedor = _service_with_fake_gateway()

    with use_tenant(tenant.id):
        _marca_e_paga_hoje(service, provedor, barber, cliente, day)
        link = service.get_or_create_public_agenda_link(actor_id=str(admin.pk))

    anon = APIClient()
    resp = anon.get(f"/api/barbershop/agenda-publica/{link.token}")
    assert resp.status_code == 200, resp.data
    assert resp.data["date"] == day
    assert len(resp.data["appointments"]) == 1
    entry = resp.data["appointments"][0]
    assert entry["barber_name"] == "Zé da Navalha"
    assert "sd_pub4" in entry["customer_name"] or entry["customer_name"]
    assert entry["start_at"]
    assert entry["status_label"]
    # Não vaza preço nem dado de pagamento — só o essencial pro barbeiro.
    assert "price" not in entry
    assert "payment" not in entry


def test_public_agenda_view_rejects_unknown_token():
    resp = APIClient().get("/api/barbershop/agenda-publica/token-que-nao-existe")
    assert resp.status_code == 422, resp.data


def test_public_agenda_view_is_tenant_isolated():
    tenant_a, admin_a = _org("pub5a")
    tenant_b, admin_b = _org("pub5b")
    day = timezone.localdate()
    barber_a = _barber_with_grid(tenant_a, admin_a, weekday=day.weekday())
    barber_b = _barber_with_grid(tenant_b, admin_b, weekday=day.weekday())
    cliente_a = _payer(tenant_a, "sd_pub5a")
    cliente_b = _payer(tenant_b, "sd_pub5b")
    service, provedor = _service_with_fake_gateway()

    with use_tenant(tenant_a.id):
        _marca_e_paga_hoje(service, provedor, barber_a, cliente_a, day)
        link_a = service.get_or_create_public_agenda_link(actor_id=str(admin_a.pk))
    with use_tenant(tenant_b.id):
        _marca_e_paga_hoje(service, provedor, barber_b, cliente_b, day)

    resp = APIClient().get(f"/api/barbershop/agenda-publica/{link_a.token}")
    assert resp.status_code == 200, resp.data
    # Só o corte do tenant A — o do tenant B não vaza, mesmo hoje/mesmo barbeiro homônimo.
    assert len(resp.data["appointments"]) == 1
    assert resp.data["appointments"][0]["customer_name"] and "sd_pub5b" not in str(
        resp.data["appointments"][0]
    )
