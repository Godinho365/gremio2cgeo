"""Sprint 3: reservas com anti-sobreposição (RN-B1), aprovação e cancelamento."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import RoleCode
from apps.accounts.services import OnboardingService, UserService
from apps.assets.services import AssetService
from apps.scheduling.models import BookingStatus
from core.context import use_tenant

pytestmark = pytest.mark.django_db


def _org(name: str):
    return OnboardingService().create_organization(
        org_name=name, admin_username=f"admin_{name}", admin_password="supersecret123"
    )


def _dt(day: int, hour: int) -> str:
    return datetime(2026, 8, day, hour, 0, tzinfo=UTC).isoformat()


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
