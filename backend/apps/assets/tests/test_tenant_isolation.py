"""Sprint 0 acceptance: tenant A must never read tenant B's data (RN-T1)."""
from __future__ import annotations

import pytest

from apps.assets.repositories import AssetRepository
from apps.assets.services import AssetService
from core.context import use_tenant
from core.exceptions import BusinessRuleError
from core.repositories import TenantIsolationError

pytestmark = pytest.mark.django_db


def test_repository_only_returns_current_tenant_data(tenant_a, tenant_b):
    repo = AssetRepository()

    with use_tenant(tenant_a.id):
        AssetService(repo).create_asset(asset_tag="PAT-A-1", name="Notebook A")

    with use_tenant(tenant_b.id):
        AssetService(repo).create_asset(asset_tag="PAT-B-1", name="Notebook B")
        tags_b = set(repo.all().values_list("asset_tag", flat=True))

    with use_tenant(tenant_a.id):
        tags_a = set(repo.all().values_list("asset_tag", flat=True))

    assert tags_a == {"PAT-A-1"}
    assert tags_b == {"PAT-B-1"}


def test_same_tag_allowed_across_tenants_but_unique_within(tenant_a, tenant_b):
    service = AssetService()
    with use_tenant(tenant_a.id):
        service.create_asset(asset_tag="PAT-1", name="A")
    # same tag in another tenant is fine
    with use_tenant(tenant_b.id):
        service.create_asset(asset_tag="PAT-1", name="B")
    # duplicate within the same tenant is rejected (RN-A1)
    with use_tenant(tenant_a.id), pytest.raises(BusinessRuleError):
        service.create_asset(asset_tag="PAT-1", name="A2")


def test_access_without_tenant_raises():
    repo = AssetRepository()
    with pytest.raises(TenantIsolationError):
        list(repo.all())
