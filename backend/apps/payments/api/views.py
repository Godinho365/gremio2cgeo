"""Webhook do Mercado Pago.

Endpoint público por natureza: quem autentica é a assinatura HMAC do cabeçalho
``x-signature``, não um token nosso. Notificação sem assinatura válida é
recusada — aceitar sem conferir deixaria qualquer um marcar um corte como pago.
"""
from __future__ import annotations

import logging

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.barbershop.models import walk_in_price
from apps.barbershop.services import BarbershopService
from core.viewsets import TenantContextAPIView

from ..credits import CreditService
from ..gateways.mercadopago import MercadoPagoGateway
from ..services import PaymentService
from .serializers import CreditBalanceSerializer

logger = logging.getLogger(__name__)


class MercadoPagoWebhookView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={200: None, 401: None})
    def post(self, request: Request) -> Response:
        gateway = MercadoPagoGateway()
        data_id = str((request.data.get("data") or {}).get("id") or "")
        if not gateway.signature_is_valid(
            data_id=data_id,
            request_id=request.headers.get("x-request-id", ""),
            signature_header=request.headers.get("x-signature", ""),
        ):
            logger.warning("Webhook do Mercado Pago com assinatura inválida (data.id=%s)", data_id)
            return Response({"error": {"code": "invalid_signature"}}, status=401)

        # Só interessa notificação de pagamento; o resto responde 200 para o
        # Mercado Pago parar de reenviar (ele reenvia por 15 min até um 200).
        if request.data.get("type") != "payment" or not data_id:
            return Response(status=200)

        payment = PaymentService().apply_provider_status(data_id)
        if payment is not None:
            BarbershopService().settle_appointment_for(payment)
        return Response(status=200)


class PaymentConfigView(APIView):
    """Diz à interface se o Pix está de pé, para ela não oferecer o que não funciona."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: None})
    def get(self, request: Request) -> Response:
        return Response(
            {
                "pix_enabled": PaymentService().is_configured(),
                # A tela mostra o preço; a fonte é o servidor, nunca o frontend.
                "walk_in_price": str(walk_in_price()),
                "pix_expiry_minutes": settings.PIX_EXPIRY_MINUTES,
            }
        )


class CreditView(TenantContextAPIView):
    """Saldo e extrato de crédito de quem está logado."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: CreditBalanceSerializer})
    def get(self, request: Request) -> Response:
        service = CreditService()
        return Response(
            CreditBalanceSerializer(
                {
                    "balance": service.balance(request.user.pk),
                    "entries": service.statement(request.user.pk),
                }
            ).data
        )
