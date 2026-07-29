"""Sprint 1: org onboarding, JWT login, RBAC, tenant-scoped user management."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import RoleCode, User
from apps.accounts.services import OnboardingService, UserService
from core.context import use_tenant

pytestmark = pytest.mark.django_db


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _make_org(name: str) -> tuple:
    return OnboardingService().create_organization(
        org_name=name, admin_username=f"admin_{name}", admin_password="supersecret123"
    )


def test_signup_creates_tenant_and_admin(client: APIClient):
    resp = client.post(
        "/api/auth/signup",
        {"org_name": "Clube X", "admin_username": "boss", "admin_password": "supersecret123"},
        format="json",
    )
    assert resp.status_code == 201
    admin = User.objects.get(username="boss")
    assert admin.tenant is not None
    assert admin.has_role(RoleCode.ADMIN)


def test_login_returns_jwt_with_tenant_and_roles(client: APIClient):
    tenant, _ = _make_org("orgx")
    resp = client.post(
        "/api/auth/token",
        {"username": "admin_orgx", "password": "supersecret123"},
        format="json",
    )
    assert resp.status_code == 200
    assert "access" in resp.data and "refresh" in resp.data


def test_admin_can_create_user(client: APIClient):
    tenant, admin = _make_org("orga")
    client.force_authenticate(admin)
    resp = client.post(
        "/api/users",
        {"username": "invA", "password": "supersecret123", "role_codes": ["inventory"]},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["roles"] == ["inventory"]


def test_non_admin_cannot_create_user(client: APIClient):
    tenant, admin = _make_org("orgb")
    with use_tenant(tenant.id):
        plain = UserService().create_user(
            username="plain", password="supersecret123", role_codes=[RoleCode.USER],
            tenant_id=tenant.id,
        )
    client.force_authenticate(plain)
    resp = client.post(
        "/api/users",
        {"username": "hacker", "password": "supersecret123"},
        format="json",
    )
    assert resp.status_code == 403


def test_user_list_is_tenant_scoped(client: APIClient):
    tenant_a, admin_a = _make_org("aaa")
    tenant_b, admin_b = _make_org("bbb")
    client.force_authenticate(admin_a)
    resp = client.get("/api/users")
    usernames = {u["username"] for u in resp.data["results"]}
    assert usernames == {"admin_aaa"}
    assert "admin_bbb" not in usernames


def test_me_returns_current_user(client: APIClient):
    tenant, admin = _make_org("meorg")
    client.force_authenticate(admin)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.data["username"] == "admin_meorg"
