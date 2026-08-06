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


def test_signup_registers_user_by_email(client: APIClient):
    tenant, _ = _make_org("Base")  # organização precisa existir
    resp = client.post(
        "/api/auth/signup",
        {
            "full_name": "João da Silva",
            "nome_guerra": "SILVA",
            "posto_graduacao": "Cap",
            "cpf": "111.444.777-35",  # CPF válido
            "birth_date": "1990-05-10",
            "email": "joao@ex.com",
            "email_confirm": "joao@ex.com",
            "phone": "(11) 99999-9999",
            "password": "supersecret123",
        },
        format="json",
    )
    assert resp.status_code == 201
    u = User.objects.get(email="joao@ex.com")
    assert u.tenant_id == tenant.id
    assert u.has_role(RoleCode.USER)
    assert u.full_name == "João da Silva"
    assert u.cpf == "11144477735"  # armazenado só com dígitos
    # login por e-mail funciona
    tok = client.post(
        "/api/auth/token",
        {"username": "joao@ex.com", "password": "supersecret123"},
        format="json",
    )
    assert tok.status_code == 200


def test_signup_rejects_invalid_cpf(client: APIClient):
    _make_org("Base2")
    resp = client.post(
        "/api/auth/signup",
        {
            "full_name": "Maria",
            "nome_guerra": "SOUZA",
            "posto_graduacao": "Sd",
            "cpf": "111.111.111-11",  # inválido
            "birth_date": "1990-05-10",
            "email": "maria@ex.com",
            "email_confirm": "maria@ex.com",
            "password": "supersecret123",
        },
        format="json",
    )
    assert resp.status_code == 400


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


def test_create_user_with_rank_and_war_name(client: APIClient):
    tenant, admin = _make_org("rank")
    client.force_authenticate(admin)
    resp = client.post(
        "/api/users",
        {
            "username": "sd_souza",
            "password": "supersecret123",
            "nome_guerra": "SOUZA",
            "posto_graduacao": "Sd",
            "role_codes": ["user"],
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["nome_guerra"] == "SOUZA"
    assert resp.data["display_name"] == "Sd SOUZA"


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
