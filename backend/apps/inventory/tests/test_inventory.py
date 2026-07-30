"""Sprint 5: inventário (Art.30 b) — abrir gera itens, conferir, divergência, fechar, relatório."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import RoleCode
from apps.accounts.services import OnboardingService, UserService
from apps.assets.models import Location
from apps.assets.services import AssetService
from apps.inventory.models import DiscrepancyType
from core.context import use_tenant

pytestmark = pytest.mark.django_db


def _org(name: str):
    return OnboardingService().create_organization(
        org_name=name, admin_username=f"admin_{name}", admin_password="supersecret123"
    )


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def test_open_generates_items_for_all_assets(client: APIClient):
    tenant, admin = _org("in1")
    with use_tenant(tenant.id):
        s = AssetService()
        s.create_asset(name="A")
        s.create_asset(name="B")
    client.force_authenticate(admin)
    inv = client.post("/api/inventories", {"title": "Anual 2026"}, format="json")
    assert inv.status_code == 201, inv.data
    items = client.get(f"/api/inventories/{inv.data['id']}/items")
    assert len(items.data) == 2


def test_scan_marks_found_and_detects_wrong_location(client: APIClient):
    tenant, admin = _org("in2")
    with use_tenant(tenant.id):
        loc1 = Location.objects.create(tenant_id=tenant.id, name="Sala 1")
        loc2 = Location.objects.create(tenant_id=tenant.id, name="Sala 2")
        AssetService().create_asset(name="Item", location=loc1)
    client.force_authenticate(admin)
    inv = client.post("/api/inventories", {"title": "Conf"}, format="json").data
    item = client.get(f"/api/inventories/{inv['id']}/items").data[0]
    # conferido em local diferente do esperado
    resp = client.post(
        f"/api/inventories/{inv['id']}/scan",
        {"item": item["id"], "found_location": str(loc2.id), "condition_found": "good"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["found"] is True
    assert resp.data["discrepancy"] == DiscrepancyType.WRONG_LOCATION


def test_report_and_close(client: APIClient):
    tenant, admin = _org("in3")
    with use_tenant(tenant.id):
        s = AssetService()
        s.create_asset(name="A")
        s.create_asset(name="B")
    client.force_authenticate(admin)
    inv = client.post("/api/inventories", {"title": "R"}, format="json").data
    items = client.get(f"/api/inventories/{inv['id']}/items").data
    client.post(
        f"/api/inventories/{inv['id']}/scan",
        {"item": items[0]["id"], "condition_found": "good"},
        format="json",
    )
    report = client.get(f"/api/inventories/{inv['id']}/report").data
    assert report == {"total": 2, "found": 1, "not_found": 1, "wrong_location": 0}
    closed = client.post(f"/api/inventories/{inv['id']}/close")
    assert closed.data["status"] == "closed"
    # não dá para conferir após fechar
    resp = client.post(
        f"/api/inventories/{inv['id']}/scan",
        {"item": items[1]["id"], "condition_found": "good"},
        format="json",
    )
    assert resp.status_code == 422


def test_inventory_role_can_scan_but_plain_user_cannot(client: APIClient):
    tenant, admin = _org("in4")
    with use_tenant(tenant.id):
        AssetService().create_asset(name="A")
        plain = UserService().create_user(
            username="plainin", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    inv = client.post("/api/inventories", {"title": "P"}, format="json").data
    client.force_authenticate(plain)
    assert client.post("/api/inventories", {"title": "X"}, format="json").status_code == 422
    item = client.get(f"/api/inventories/{inv['id']}/items").data[0]
    resp = client.post(
        f"/api/inventories/{inv['id']}/scan",
        {"item": item["id"], "condition_found": "good"},
        format="json",
    )
    assert resp.status_code == 422


def test_inventories_tenant_scoped(client: APIClient):
    ta, admin_a = _org("inA")
    tb, admin_b = _org("inB")
    client.force_authenticate(admin_b)
    client.post("/api/inventories", {"title": "B"}, format="json")
    client.force_authenticate(admin_a)
    assert client.get("/api/inventories").data["count"] == 0
