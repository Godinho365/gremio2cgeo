"""Sprint 4: cautelas (Art.30 d) — emissão assinada, devolução com inspeção, regras."""
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


def _issue_payload(asset, holder, **over):
    base = {
        "asset": str(asset.id),
        "holder": str(holder.pk),
        "due_at": _due(),
        "condition_out": "good",
        "holder_signature": True,
        "issuer_signature": True,
    }
    base.update(over)
    return base


def test_issue_custody_sets_asset_in_use(client: APIClient):
    tenant, admin = _org("cu1")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    resp = client.post("/api/custodies", _issue_payload(asset, admin), format="json")
    assert resp.status_code == 201, resp.data
    assert resp.data["status"] == CustodyStatus.ACTIVE
    assert resp.data["term_hash"]  # termo com hash (trilha)
    asset.refresh_from_db()
    assert asset.status == AssetStatus.IN_USE


def test_issue_requires_both_signatures(client: APIClient):
    tenant, admin = _org("cu2")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    resp = client.post(
        "/api/custodies",
        _issue_payload(asset, admin, holder_signature=False),
        format="json",
    )
    assert resp.status_code == 422  # RN-C1
    assert resp.data["error"]["code"] == "missing_signature"


def test_only_one_open_custody_per_asset(client: APIClient):
    tenant, admin = _org("cu3")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    first = client.post("/api/custodies", _issue_payload(asset, admin), format="json")
    assert first.status_code == 201
    # 2ª emissão barrada: bem já está em uso / com cautela aberta (RN-C2 + status).
    resp = client.post("/api/custodies", _issue_payload(asset, admin), format="json")
    assert resp.status_code == 422
    assert resp.data["error"]["code"] in ("custody_open", "asset_not_issuable")


def test_non_manager_cannot_issue(client: APIClient):
    tenant, admin = _org("cu4")
    asset = _asset(tenant)
    with use_tenant(tenant.id):
        plain = UserService().create_user(
            username="plaincu", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(plain)
    resp = client.post("/api/custodies", _issue_payload(asset, plain), format="json")
    assert resp.status_code == 422
    assert resp.data["error"]["code"] == "forbidden"


def test_return_ok_makes_asset_available(client: APIClient):
    tenant, admin = _org("cu5")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    cid = client.post("/api/custodies", _issue_payload(asset, admin), format="json").data["id"]
    resp = client.post(
        f"/api/custodies/{cid}/return",
        {"condition_in": "good", "outcome": "ok"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["status"] == CustodyStatus.RETURNED
    asset.refresh_from_db()
    assert asset.status == AssetStatus.AVAILABLE


def test_return_with_damage_sends_to_maintenance(client: APIClient):
    tenant, admin = _org("cu6")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    cid = client.post("/api/custodies", _issue_payload(asset, admin), format="json").data["id"]
    resp = client.post(
        f"/api/custodies/{cid}/return",
        {"condition_in": "bad", "outcome": "damage"},
        format="json",
    )
    assert resp.status_code == 200
    asset.refresh_from_db()
    assert asset.status == AssetStatus.MAINTENANCE  # RN-C5


def test_return_missing_marks_lost(client: APIClient):
    tenant, admin = _org("cu7")
    asset = _asset(tenant)
    client.force_authenticate(admin)
    cid = client.post("/api/custodies", _issue_payload(asset, admin), format="json").data["id"]
    resp = client.post(
        f"/api/custodies/{cid}/return",
        {"condition_in": "regular", "outcome": "missing"},
        format="json",
    )
    assert resp.data["status"] == CustodyStatus.LOST  # RN-C5


def test_mark_overdue_job(client: APIClient):
    tenant, admin = _org("cu8")
    asset = _asset(tenant)
    with use_tenant(tenant.id):
        custody = Custody.objects.create(
            tenant_id=tenant.id, asset=asset, holder=admin, issued_by=admin,
            due_at=timezone.now() - timedelta(hours=1), condition_out="good",
            status=CustodyStatus.ACTIVE, holder_signed_at=timezone.now(),
            issuer_signed_at=timezone.now(),
        )
    assert mark_overdue_custodies() == 1  # RN-C4
    custody.refresh_from_db()
    assert custody.status == CustodyStatus.OVERDUE


def test_custodies_are_tenant_scoped(client: APIClient):
    ta, admin_a = _org("cuA")
    tb, admin_b = _org("cuB")
    asset_b = _asset(tb, "BemB")
    client.force_authenticate(admin_b)
    client.post("/api/custodies", _issue_payload(asset_b, admin_b), format="json")
    client.force_authenticate(admin_a)
    assert client.get("/api/custodies").data["count"] == 0
