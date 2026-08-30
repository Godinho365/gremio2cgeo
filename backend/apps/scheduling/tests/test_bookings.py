"""Sprint 3: reservas com anti-sobreposição (RN-B1), aprovação e cancelamento."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from rest_framework.test import APIClient

from django.utils import timezone

from apps.accounts.models import RoleCode
from apps.accounts.services import OnboardingService, UserService
from apps.assets.services import AssetService
from apps.finance.models import PlanCode
from apps.finance.services import FinanceService
from apps.scheduling.models import Booking, BookingStatus
from apps.scheduling.services import BookingService
from core.context import use_tenant
from core.exceptions import BusinessRuleError

pytestmark = pytest.mark.django_db


def _org(name: str):
    return OnboardingService().create_organization(
        org_name=name, admin_username=f"admin_{name}", admin_password="supersecret123"
    )


def _make_associado(tenant, user):
    """Dá ao usuário um BillingProfile Associado Full ativo e em dia — fora
    da gestão, é isso que agora habilita reservar bens do patrimônio."""
    with use_tenant(tenant.id):
        if not user.posto_graduacao:
            user.posto_graduacao = "Cel"
            user.save(update_fields=["posto_graduacao"])
        FinanceService().activate_billing(
            user=user,
            plan=PlanCode.ASSOCIADO,
            due_day=timezone.localdate().day,
            started_period=timezone.localdate().replace(day=1),
        )


def _dt(day: int, hour: int) -> str:
    """Data futura: `day` é o deslocamento em dias a partir de hoje (reserva no passado é rejeitada)."""
    base = datetime.now(UTC) + timedelta(days=day)
    return base.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _asset(tenant, name="Bem"):
    with use_tenant(tenant.id):
        return AssetService().create_asset(name=name)


def test_create_booking(client: APIClient):
    tenant, admin = _org("bk1")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    resp = client.post(
        "/api/bookings",
        {"asset": str(asset.id), "start_at": _dt(1, 10), "end_at": _dt(1, 12)},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["status"] == BookingStatus.PENDING


def test_overlapping_booking_is_rejected(client: APIClient):
    tenant, admin = _org("bk2")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    first = {"asset": str(asset.id), "start_at": _dt(1, 10), "end_at": _dt(1, 12)}
    assert client.post("/api/bookings", first, format="json").status_code == 201
    # overlaps 11:00-13:00
    overlap = {"asset": str(asset.id), "start_at": _dt(1, 11), "end_at": _dt(1, 13)}
    resp = client.post("/api/bookings", overlap, format="json")
    assert resp.status_code == 409  # RN-B1
    assert resp.data["error"]["code"] == "booking_overlap"


def test_adjacent_booking_is_allowed(client: APIClient):
    tenant, admin = _org("bk3")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    client.post(
        "/api/bookings",
        {"asset": str(asset.id), "start_at": _dt(1, 10), "end_at": _dt(1, 12)},
        format="json",
    )
    # starts exactly when the previous ends -> no overlap
    resp = client.post(
        "/api/bookings",
        {"asset": str(asset.id), "start_at": _dt(1, 12), "end_at": _dt(1, 14)},
        format="json",
    )
    assert resp.status_code == 201


def test_approve_requires_manager(client: APIClient):
    tenant, admin = _org("bk4")
    asset = _asset(tenant)
    with use_tenant(tenant.id):
        plain = UserService().create_user(
            username="plain4", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    _make_associado(tenant, plain)
    client.force_authenticate(plain)
    created = client.post(
        "/api/bookings",
        {"asset": str(asset.id), "start_at": _dt(2, 10), "end_at": _dt(2, 12)},
        format="json",
    )
    bid = created.data["id"]
    # plain user cannot approve
    assert client.post(f"/api/bookings/{bid}/approve").status_code == 422
    # admin can
    client.force_authenticate(admin)
    resp = client.post(f"/api/bookings/{bid}/approve")
    assert resp.status_code == 200
    assert resp.data["status"] == BookingStatus.APPROVED


def test_cancelled_slot_frees_up(client: APIClient):
    tenant, admin = _org("bk5")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    b1 = client.post(
        "/api/bookings",
        {"asset": str(asset.id), "start_at": _dt(3, 10), "end_at": _dt(3, 12)},
        format="json",
    ).data
    client.post(f"/api/bookings/{b1['id']}/cancel")
    # same slot now free
    resp = client.post(
        "/api/bookings",
        {"asset": str(asset.id), "start_at": _dt(3, 10), "end_at": _dt(3, 12)},
        format="json",
    )
    assert resp.status_code == 201


def test_cancel_is_restricted_to_owner_or_manager(client: APIClient):
    """Dono cancela a própria; terceiro não mexe na reserva alheia; gestor cancela qualquer uma."""
    tenant, admin = _org("bk6")
    asset = _asset(tenant)
    with use_tenant(tenant.id):
        dono = UserService().create_user(
            username="dono6", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
        outro = UserService().create_user(
            username="outro6", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    _make_associado(tenant, dono)

    client.force_authenticate(dono)
    bid = client.post(
        "/api/bookings",
        {"asset": str(asset.id), "start_at": _dt(5, 10), "end_at": _dt(5, 12)},
        format="json",
    ).data["id"]

    client.force_authenticate(outro)
    recusado = client.post(f"/api/bookings/{bid}/cancel")
    assert recusado.status_code == 422
    assert recusado.data["error"]["code"] == "forbidden"

    client.force_authenticate(dono)
    assert client.post(f"/api/bookings/{bid}/cancel").status_code == 200

    # gestor cancela reserva de terceiro
    client.force_authenticate(dono)
    outro_id = client.post(
        "/api/bookings",
        {"asset": str(asset.id), "start_at": _dt(6, 10), "end_at": _dt(6, 12)},
        format="json",
    ).data["id"]
    client.force_authenticate(admin)
    assert client.post(f"/api/bookings/{outro_id}/cancel").status_code == 200


def test_upcoming_filter_hides_finished_bookings(client: APIClient):
    """A fila de reservas (dashboard/cautelas) não pode encher de reservas já encerradas."""
    tenant, admin = _org("bk7")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    futura = client.post(
        "/api/bookings",
        {"asset": str(asset.id), "start_at": _dt(7, 10), "end_at": _dt(8, 12)},
        format="json",
    ).data
    # encerrada: criada pelo service para poder ficar no passado
    with use_tenant(tenant.id):
        antiga = Booking.objects.create(
            tenant_id=tenant.id,
            asset=asset,
            requester=admin,
            start_at=datetime.now(UTC) - timedelta(days=5),
            end_at=datetime.now(UTC) - timedelta(days=4),
            status=BookingStatus.APPROVED,
        )

    todas = {b["id"] for b in client.get("/api/bookings").data["results"]}
    assert {futura["id"], str(antiga.id)} <= todas

    em_curso = {b["id"] for b in client.get("/api/bookings?upcoming=1").data["results"]}
    assert futura["id"] in em_curso
    assert str(antiga.id) not in em_curso


def test_manager_books_for_another_user(client: APIClient):
    tenant, admin = _org("bk8")
    asset = _asset(tenant)
    with use_tenant(tenant.id):
        beneficiario = UserService().create_user(
            username="benef8", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    _make_associado(tenant, beneficiario)
    client.force_authenticate(admin)
    resp = client.post(
        "/api/bookings",
        {
            "asset": str(asset.id),
            "requester": str(beneficiario.id),
            "start_at": _dt(9, 10),
            "end_at": _dt(9, 12),
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["requester"] == str(beneficiario.id)
    # gestor segue podendo aprovar a reserva que abriu para o outro
    assert client.post(f"/api/bookings/{resp.data['id']}/approve").status_code == 200


def test_plain_user_cannot_book_for_another(client: APIClient):
    tenant, admin = _org("bk9")
    asset = _asset(tenant)
    with use_tenant(tenant.id):
        comum = UserService().create_user(
            username="comum9", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(comum)
    resp = client.post(
        "/api/bookings",
        {
            "asset": str(asset.id),
            "requester": str(admin.id),  # tentando reservar em nome do admin
            "start_at": _dt(10, 10),
            "end_at": _dt(10, 12),
        },
        format="json",
    )
    assert resp.status_code == 422
    assert resp.data["error"]["code"] == "forbidden"


def test_delete_booking_is_manager_only(client: APIClient):
    tenant, admin = _org("bk10")
    asset = _asset(tenant)
    with use_tenant(tenant.id):
        comum = UserService().create_user(
            username="comum10", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    _make_associado(tenant, comum)
    client.force_authenticate(comum)
    bid = client.post(
        "/api/bookings",
        {"asset": str(asset.id), "start_at": _dt(11, 10), "end_at": _dt(11, 12)},
        format="json",
    ).data["id"]

    assert client.delete(f"/api/bookings/{bid}").status_code == 422  # dono não exclui

    client.force_authenticate(admin)
    assert client.delete(f"/api/bookings/{bid}").status_code == 204
    assert bid not in {b["id"] for b in client.get("/api/bookings").data["results"]}


def test_bookings_are_tenant_scoped(client: APIClient):
    ta, admin_a = _org("bkA")
    tb, admin_b = _org("bkB")
    asset_b = _asset(tb, "BemB")
    client.force_authenticate(admin_b)
    client.post(
        "/api/bookings",
        {"asset": str(asset_b.id), "start_at": _dt(4, 10), "end_at": _dt(4, 12)},
        format="json",
    )
    client.force_authenticate(admin_a)
    resp = client.get("/api/bookings")
    assert resp.data["count"] == 0


def test_barbershop_client_cannot_book_or_read_availability(client: APIClient):
    tenant, admin = _org("bk8")
    asset = _asset(tenant)
    with use_tenant(tenant.id):
        cliente = UserService().create_user(
            username="cliente_bk8", password="supersecret123",
            role_codes=[RoleCode.BARBERSHOP_CLIENT], tenant_id=tenant.id,
        )
    client.force_authenticate(cliente)
    resp = client.post(
        "/api/bookings",
        {"asset": str(asset.id), "start_at": _dt(1, 10), "end_at": _dt(1, 12)},
        format="json",
    )
    assert resp.status_code == 403
    assert client.get("/api/availabilities").status_code == 403


def test_plain_user_can_still_read_availabilities(client: APIClient):
    tenant, admin = _org("bk9")
    with use_tenant(tenant.id):
        plain = UserService().create_user(
            username="plain9", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(plain)
    assert client.get("/api/availabilities").status_code == 200


# ── Associado Full em dia é exigido pra reservar (fora da gestão) ───────────


def test_user_without_any_plan_cannot_book(client: APIClient):
    tenant, admin = _org("bk11")
    asset = _asset(tenant)
    with use_tenant(tenant.id):
        sem_plano = UserService().create_user(
            username="sem_plano11", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(sem_plano)
    resp = client.post(
        "/api/bookings",
        {"asset": str(asset.id), "start_at": _dt(12, 10), "end_at": _dt(12, 12)},
        format="json",
    )
    assert resp.status_code == 422, resp.data
    assert resp.data["error"]["code"] == "associado_full_required"


def test_barbearia_plan_does_not_unlock_reservations():
    """Assinatura Barbearia é só pra Barbearia — não dá acesso ao patrimônio.

    Testa o service direto, não a API: na prática o role de Cb/Sd EP/Sd EV já
    é forçado pra "Cliente da Barbearia" (barra antes mesmo de chegar aqui),
    mas a regra do plano precisa valer por si só — defesa em profundidade,
    não depender só da camada de permissão da view.
    """
    tenant, admin = _org("bk12")
    asset = _asset(tenant)
    with use_tenant(tenant.id):
        cb = UserService().create_user(
            username="cb12", password="supersecret123",
            posto_graduacao="Cb", tenant_id=tenant.id,
        )
        FinanceService().activate_billing(
            user=cb, plan=PlanCode.BARBEARIA, due_day=timezone.localdate().day,
            started_period=timezone.localdate().replace(day=1),
        )
        inicio = datetime.now(UTC) + timedelta(days=13)
        with pytest.raises(BusinessRuleError):
            BookingService().create_booking(
                asset_id=asset.id,
                requester_id=str(cb.id),
                start_at=inicio.replace(hour=10, minute=0, second=0, microsecond=0),
                end_at=inicio.replace(hour=12, minute=0, second=0, microsecond=0),
            )


def test_delinquent_associado_cannot_book(client: APIClient):
    from apps.finance.models import BillingProfile, FinancialStatus

    tenant, admin = _org("bk13")
    asset = _asset(tenant)
    with use_tenant(tenant.id):
        atrasado = UserService().create_user(
            username="atrasado13", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    _make_associado(tenant, atrasado)
    with use_tenant(tenant.id):
        perfil = BillingProfile.objects.get(user=atrasado)
        perfil.financial_status = FinancialStatus.DELINQUENT
        perfil.save(update_fields=["financial_status"])

    client.force_authenticate(atrasado)
    resp = client.post(
        "/api/bookings",
        {"asset": str(asset.id), "start_at": _dt(14, 10), "end_at": _dt(14, 12)},
        format="json",
    )
    assert resp.status_code == 422, resp.data
    assert resp.data["error"]["code"] == "associado_full_required"


def test_management_roles_are_exempt_from_the_associado_full_requirement(client: APIClient):
    """Diretor/Inventariante/Auditor reservam mesmo sem plano — só admin não
    basta sozinho pra provar a isenção (o teste já cobre admin em outros lugares)."""
    tenant, admin = _org("bk14")
    asset = _asset(tenant)
    with use_tenant(tenant.id):
        diretor = UserService().create_user(
            username="diretor14", password="supersecret123",
            role_codes=[RoleCode.DIRECTOR], tenant_id=tenant.id,
        )
    client.force_authenticate(diretor)
    resp = client.post(
        "/api/bookings",
        {"asset": str(asset.id), "start_at": _dt(15, 10), "end_at": _dt(15, 12)},
        format="json",
    )
    assert resp.status_code == 201, resp.data


def test_associado_full_em_dia_can_book(client: APIClient):
    tenant, admin = _org("bk15")
    asset = _asset(tenant)
    with use_tenant(tenant.id):
        associado = UserService().create_user(
            username="associado15", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    _make_associado(tenant, associado)
    client.force_authenticate(associado)
    resp = client.post(
        "/api/bookings",
        {"asset": str(asset.id), "start_at": _dt(16, 10), "end_at": _dt(16, 12)},
        format="json",
    )
    assert resp.status_code == 201, resp.data
