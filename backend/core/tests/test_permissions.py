"""Unit tests for reusable RBAC permissions."""
from __future__ import annotations

import pytest
from rest_framework.test import APIRequestFactory

from apps.accounts.models import RoleCode
from apps.accounts.services import OnboardingService, UserService
from core.context import use_tenant
from core.permissions import ExcludesRoles

pytestmark = pytest.mark.django_db


class _FakeView:
    excluded_roles = (RoleCode.BARBERSHOP_CLIENT,)


def _org(name: str):
    return OnboardingService().create_organization(
        org_name=name, admin_username=f"admin_{name}", admin_password="supersecret123"
    )


def test_excludes_roles_allows_superuser_even_if_excluded_role_present():
    tenant, admin = _org("perm1")
    with use_tenant(tenant.id):
        superuser = UserService().create_user(
            username="root_perm1", password="supersecret123",
            role_codes=[RoleCode.BARBERSHOP_CLIENT], tenant_id=tenant.id,
        )
    superuser.is_superuser = True
    superuser.save(update_fields=["is_superuser"])
    request = APIRequestFactory().get("/")
    request.user = superuser
    assert ExcludesRoles().has_permission(request, _FakeView()) is True


def test_excludes_roles_denies_unauthenticated():
    request = APIRequestFactory().get("/")

    class _Anon:
        is_authenticated = False

    request.user = _Anon()
    assert ExcludesRoles().has_permission(request, _FakeView()) is False


def test_excludes_roles_allows_all_when_no_excluded_roles_declared():
    tenant, admin = _org("perm2")
    with use_tenant(tenant.id):
        cliente = UserService().create_user(
            username="cliente_perm2", password="supersecret123",
            role_codes=[RoleCode.BARBERSHOP_CLIENT], tenant_id=tenant.id,
        )
    request = APIRequestFactory().get("/")
    request.user = cliente

    class _ViewWithNoExclusion:
        pass

    assert ExcludesRoles().has_permission(request, _ViewWithNoExclusion()) is True
