from __future__ import annotations

import pytest

from core.models import Tenant


@pytest.fixture
def tenant_a(db) -> Tenant:
    return Tenant.objects.create(name="Org A", slug="org-a")


@pytest.fixture
def tenant_b(db) -> Tenant:
    return Tenant.objects.create(name="Org B", slug="org-b")
