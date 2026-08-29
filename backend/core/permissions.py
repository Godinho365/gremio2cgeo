"""Reusable RBAC permissions. Roles: docs/produto/personas-perfis.md.

A view declares ``required_roles`` (tuple of RoleCode values). Superusers bypass.
When ``required_roles`` is empty, any authenticated user passes.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.permissions import BasePermission

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView


class HasAnyRole(BasePermission):
    message = "Você não tem o perfil necessário para esta ação."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        required: tuple[str, ...] = tuple(getattr(view, "required_roles", ()))
        if not required:
            return True
        return user.roles.filter(code__in=required).exists()


class ExcludesRoles(BasePermission):
    """Espelho de ``HasAnyRole``: nega acesso a quem tem algum papel listado
    em ``excluded_roles`` (atributo da view). Sem esse atributo, libera geral.
    """

    message = "Este perfil não tem acesso a este recurso."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        excluded: tuple[str, ...] = tuple(getattr(view, "excluded_roles", ()))
        if not excluded:
            return True
        return not user.roles.filter(code__in=excluded).exists()
