"""Domain exceptions + a DRF handler that renders the standard error envelope.

Envelope contract: docs/api/convencoes.md.
"""
from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class BusinessRuleError(Exception):
    """Raised by services when a business invariant (RN-xx) is violated -> 422."""

    def __init__(self, message: str, code: str = "business_rule_error") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, BusinessRuleError):
        return Response(
            {"error": {"code": exc.code, "message": exc.message}},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    code = "error"
    if isinstance(detail, dict) and "detail" in detail:
        message, fields = str(detail["detail"]), {}
    elif isinstance(detail, dict):
        message, fields = "Erro de validação.", detail
    else:
        message, fields = "Erro.", {}

    response.data = {"error": {"code": code, "message": message, "fields": fields}}
    return response
