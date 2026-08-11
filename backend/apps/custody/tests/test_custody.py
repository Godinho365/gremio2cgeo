"""Sprint 4: cautelas (Art.30 d) — solicitar, aprovar/rejeitar/excluir, devolver."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import RoleCode
from apps.accounts.services import OnboardingService, UserService
from apps.assets.models import AssetStatus
from apps.assets.services import AssetService
from apps.custody.models import Custody, CustodyStatus
from apps.custody.services import mark_overdue_custodies
from core.context import use_tenant

pytestmark = pytest.mark.django_db


def _org(name: str):
    return OnboardingService().create_organization(
        org_name=name, admin_username=f"admin_{name}", admin_password="supersecret123"
    )


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _asset(tenant, name="Bem"):
    with use_tenant(tenant.id):
        return AssetService().create_asset(name=name)


def _due():
    return (timezone.now() + timedelta(days=3)).isoformat()


def _payload(asset, holder):
    return {
        "asset": str(asset.id),
        "holder": str(holder.pk),
        "due_at": _due(),
        "condition_out": "good",
    }


def _plain(tenant, suffix: str):
    with use_tenant(tenant.id):
        return UserService().create_user(
            username=f"plain_{suffix}", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )


def test_manager_delivery_creates_active_custody(client: APIClient):
    """Gestor entrega o bem: a cautela já nasce ativa, sem etapa de aprovação."""
    tenant, admin = _org("cu1")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    resp = client.post("/api/custodies", _payload(asset, admin), format="json")
    assert resp.status_code == 201, resp.data
    assert resp.data["status"] == CustodyStatus.ACTIVE
    assert resp.data["term_hash"]
    asset.refresh_from_db()
    assert asset.status == AssetStatus.IN_USE


def test_delivery_records_the_informed_date(client: APIClient):
    tenant, admin = _org("cu1b")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    ontem = timezone.now() - timedelta(days=1)
    resp = client.post(
        "/api/custodies", {**_payload(asset, admin), "issued_at": ontem.isoformat()}, format="json"
    )
    assert resp.status_code == 201, resp.data
    entregue = Custody.objects.get(pk=resp.data["id"]).issued_at
    assert timezone.localtime(entregue).date() == timezone.localtime(ontem).date()


def test_delivery_rejects_future_date(client: APIClient):
    tenant, admin = _org("cu1c")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    amanha = timezone.now() + timedelta(days=1)
    resp = client.post(
        "/api/custodies", {**_payload(asset, admin), "issued_at": amanha.isoformat()}, format="json"
    )
    assert resp.status_code == 422
    assert resp.data["error"]["code"] == "issued_at_in_future"


def test_plain_user_request_stays_pending(client: APIClient):
    tenant, admin = _org("cu1d")
    asset = _asset(tenant)
    plain = _plain(tenant, "cu1d")
    client.force_authenticate(plain)
    resp = client.post("/api/custodies", _payload(asset, plain), format="json")
    assert resp.status_code == 201, resp.data
    assert resp.data["status"] == CustodyStatus.PENDING
    asset.refresh_from_db()
    assert asset.status == AssetStatus.AVAILABLE  # solicitação não ocupa o bem


def test_approve_activates_and_sets_in_use(client: APIClient):
    tenant, admin = _org("cu2")
    asset = _asset(tenant)
    plain = _plain(tenant, "cu2")
    client.force_authenticate(plain)
    cid = client.post("/api/custodies", _payload(asset, plain), format="json").data["id"]
    client.force_authenticate(admin)
    resp = client.post(f"/api/custodies/{cid}/approve")
    assert resp.status_code == 200
    assert resp.data["status"] == CustodyStatus.ACTIVE
    assert resp.data["term_hash"]
    asset.refresh_from_db()
    assert asset.status == AssetStatus.IN_USE


def test_reject_custody(client: APIClient):
    tenant, admin = _org("cu3")
    asset = _asset(tenant)
    plain = _plain(tenant, "cu3")
    client.force_authenticate(plain)
    cid = client.post("/api/custodies", _payload(asset, plain), format="json").data["id"]
    client.force_authenticate(admin)
    resp = client.post(f"/api/custodies/{cid}/reject")
    assert resp.status_code == 200
    assert resp.data["status"] == CustodyStatus.REJECTED


def test_delete_custody_soft(client: APIClient):
    tenant, admin = _org("cu4")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    cid = client.post("/api/custodies", _payload(asset, admin), format="json").data["id"]
    assert client.delete(f"/api/custodies/{cid}").status_code == 204
    assert client.get("/api/custodies").data["count"] == 0


def test_non_manager_cannot_approve(client: APIClient):
    tenant, admin = _org("cu5")
    asset = _asset(tenant)
    with use_tenant(tenant.id):
        plain = UserService().create_user(
            username="plaincu", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    # usuário comum pode solicitar
    client.force_authenticate(plain)
    cid = client.post("/api/custodies", _payload(asset, plain), format="json").data["id"]
    # mas não pode aprovar
    assert client.post(f"/api/custodies/{cid}/approve").status_code == 422


def test_cannot_deliver_twice_for_same_asset(client: APIClient):
    tenant, admin = _org("cu6")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    client.post("/api/custodies", _payload(asset, admin), format="json")
    # bem já entregue (cautela ativa) → segunda entrega barrada (RN-C2)
    resp = client.post("/api/custodies", _payload(asset, admin), format="json")
    assert resp.status_code == 422
    assert resp.data["error"]["code"] == "custody_already_requested"


def test_filter_open_brings_active_and_overdue(client: APIClient):
    """O card "Ativos" da tela filtra por este recorte: bem ainda com a pessoa."""
    tenant, admin = _org("cuopen")
    ativa = _asset(tenant, "Ativa")
    atrasada = _asset(tenant, "Atrasada")
    devolvida = _asset(tenant, "Devolvida")
    client.force_authenticate(admin)

    client.post("/api/custodies", _payload(ativa, admin), format="json")
    cid_atras = client.post("/api/custodies", _payload(atrasada, admin), format="json").data["id"]
    cid_dev = client.post("/api/custodies", _payload(devolvida, admin), format="json").data["id"]
    Custody.objects.filter(pk=cid_atras).update(status=CustodyStatus.OVERDUE)
    client.post(
        f"/api/custodies/{cid_dev}/return", {"condition_in": "good", "outcome": "ok"}, format="json"
    )

    em_aberto = client.get("/api/custodies?status=open").data["results"]
    assert {c["asset_name"] for c in em_aberto} == {"Ativa", "Atrasada"}


def test_return_ok_makes_available(client: APIClient):
    tenant, admin = _org("cu7")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    cid = client.post("/api/custodies", _payload(asset, admin), format="json").data["id"]
    resp = client.post(
        f"/api/custodies/{cid}/return", {"condition_in": "good", "outcome": "ok"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.data["status"] == CustodyStatus.RETURNED
    asset.refresh_from_db()
    assert asset.status == AssetStatus.AVAILABLE


def test_return_damage_to_maintenance(client: APIClient):
    tenant, admin = _org("cu8")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    cid = client.post("/api/custodies", _payload(asset, admin), format="json").data["id"]
    client.post(
        f"/api/custodies/{cid}/return", {"condition_in": "bad", "outcome": "damage"}, format="json"
    )
    asset.refresh_from_db()
    assert asset.status == AssetStatus.MAINTENANCE  # RN-C5


def test_mark_overdue_job(client: APIClient):
    tenant, admin = _org("cu9")
    asset = _asset(tenant)
    with use_tenant(tenant.id):
        custody = Custody.objects.create(
            tenant_id=tenant.id, asset=asset, holder=admin, issued_by=admin,
            due_at=timezone.now() - timedelta(hours=1), condition_out="good",
            status=CustodyStatus.ACTIVE,
        )
    assert mark_overdue_custodies() == 1  # RN-C4
    custody.refresh_from_db()
    assert custody.status == CustodyStatus.OVERDUE


def test_custodies_tenant_scoped(client: APIClient):
    ta, admin_a = _org("cuA")
    tb, admin_b = _org("cuB")
    asset_b = _asset(tb, "BemB")
    client.force_authenticate(admin_b)
    client.post("/api/custodies", _payload(asset_b, admin_b), format="json")
    client.force_authenticate(admin_a)
    assert client.get("/api/custodies").data["count"] == 0
