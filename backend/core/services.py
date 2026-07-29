"""Base service. Business logic lives here (and only here).

Services orchestrate repositories, enforce invariants (RN-xx), and run inside
transactions. They must not know about HTTP (request/response).
"""
from __future__ import annotations


class BaseService:
    """Marker base for services. Extend per domain (e.g. AssetService)."""
