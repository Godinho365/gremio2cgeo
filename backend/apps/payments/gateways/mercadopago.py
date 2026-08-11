"""Cliente do Mercado Pago (Pix pela API de Payments).

Referência: POST https://api.mercadopago.com/v1/payments com
``payment_method_id: "pix"``; o QR volta em
``point_of_interaction.transaction_data``. A confirmação chega por webhook
assinado (HMAC-SHA256) e também pode ser consultada em GET /v1/payments/{id}.

Usa urllib da biblioteca padrão de propósito: são dois endpoints e não vale
puxar uma dependência nova para dentro da imagem por causa disso.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .base import PayerInfo, PaymentGatewayError, PixCharge

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://api.mercadopago.com"
TIMEOUT_SECONDS = 20

# Como o Mercado Pago nomeia as situações → nosso PaymentStatus.
STATUS_MAP = {
    "pending": "pending",
    "in_process": "pending",
    "authorized": "pending",
    "approved": "approved",
    "rejected": "rejected",
    "cancelled": "cancelled",
    "refunded": "refunded",
    "charged_back": "refunded",
    "in_mediation": "pending",
}


class MercadoPagoGateway:
    name = "mercadopago"

    def __init__(self, access_token: str | None = None, webhook_secret: str | None = None) -> None:
        self._access_token = access_token
        self._webhook_secret = webhook_secret

    # Lidas na hora do uso, não no __init__: quem monta o gateway pode ser um
    # objeto de vida longa (o ViewSet monta o service na definição da classe),
    # e aí uma credencial capturada cedo demais nunca mais seria atualizada.
    @property
    def access_token(self) -> str:
        if self._access_token is not None:
            return self._access_token
        return settings.MERCADOPAGO_ACCESS_TOKEN

    @property
    def api_base(self) -> str:
        """Endereço da API. Só muda para apontar para um ambiente de ensaio."""
        return getattr(settings, "MERCADOPAGO_API_BASE", "") or DEFAULT_API_BASE

    @property
    def webhook_secret(self) -> str:
        if self._webhook_secret is not None:
            return self._webhook_secret
        return settings.MERCADOPAGO_WEBHOOK_SECRET

    def is_configured(self) -> bool:
        return bool(self.access_token)

    def _require_token(self) -> str:
        if not self.access_token:
            raise PaymentGatewayError(
                "O pagamento por Pix ainda não foi configurado nesta instalação.",
                code="payments_not_configured",
            )
        return self.access_token

    # ── HTTP ────────────────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict | None = None,
        headers: dict | None = None,
    ) -> dict:
        token = self._require_token()
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{self.api_base}{path}", data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            req.add_header(key, value)

        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            detalhe = self._error_detail(exc)
            # Nunca vaza o corpo cru para o usuário: pode conter dado do pagador.
            logger.warning("Mercado Pago %s %s -> %s: %s", method, path, exc.code, detalhe)
            raise PaymentGatewayError(
                f"O Mercado Pago recusou a cobrança ({detalhe}).", code="gateway_rejected"
            ) from exc
        except urllib.error.URLError as exc:
            logger.warning("Mercado Pago %s %s indisponível: %s", method, path, exc)
            raise PaymentGatewayError(
                "Não foi possível falar com o Mercado Pago agora. Tente de novo.",
                code="gateway_unavailable",
            ) from exc

    # Recados do Mercado Pago que não dizem nada a quem está usando o sistema.
    # A chave é um trecho da mensagem original (em minúsculas).
    _EXPLICACOES = {
        "unauthorized use of live credentials": (
            "As duas pontas precisam ser do mesmo tipo: conta de teste cobra de "
            "pagador de teste, conta real cobra de pagador real. Confira se o "
            "token em MERCADOPAGO_ACCESS_TOKEN é da conta certa."
        ),
        "one of the parties": (
            "Uma das partes é de teste e a outra é real. Use credenciais da conta "
            "real para cobrar de pessoas reais."
        ),
        "invalid payment_method_id": (
            "O Pix não está habilitado nesta conta do Mercado Pago. Cadastre uma "
            "chave Pix no aplicativo e conclua a validação da conta."
        ),
        "invalid users involved": (
            "O pagador e o recebedor são a mesma conta do Mercado Pago — ninguém "
            "paga a si mesmo. Use outro e-mail no perfil de quem está marcando."
        ),
    }

    @classmethod
    def _error_detail(cls, exc: urllib.error.HTTPError) -> str:
        try:
            payload = json.loads(exc.read() or b"{}")
        except (ValueError, OSError):
            return f"HTTP {exc.code}"
        bruto = str(payload.get("message") or payload.get("error") or f"HTTP {exc.code}")
        for trecho, explicacao in cls._EXPLICACOES.items():
            if trecho in bruto.lower():
                # Mantém o texto original junto: é o que o suporte deles pede.
                return f"{explicacao} (Mercado Pago: {bruto})"
        return bruto

    # ── Cobrança Pix ────────────────────────────────────────────────────────

    def create_pix_charge(
        self,
        *,
        amount: Decimal,
        description: str,
        payer: PayerInfo,
        expires_in_minutes: int,
        idempotency_key: str,
        notification_url: str | None = None,
        external_reference: str = "",
    ) -> PixCharge:
        expira = timezone.localtime(timezone.now() + timedelta(minutes=expires_in_minutes))
        body: dict = {
            "transaction_amount": float(amount),
            "description": description,
            "payment_method_id": "pix",
            "date_of_expiration": expira.isoformat(timespec="milliseconds"),
            "payer": {
                "email": payer.email,
                "first_name": payer.first_name,
                "last_name": payer.last_name,
            },
        }
        if payer.cpf:
            body["payer"]["identification"] = {"type": "CPF", "number": payer.cpf}
        if notification_url:
            body["notification_url"] = notification_url
        if external_reference:
            body["external_reference"] = external_reference

        data = self._request(
            "POST", "/v1/payments", body=body, headers={"X-Idempotency-Key": idempotency_key}
        )
        transacao = (data.get("point_of_interaction") or {}).get("transaction_data") or {}
        return PixCharge(
            provider_payment_id=str(data.get("id", "")),
            status=str(data.get("status", "")),
            status_detail=str(data.get("status_detail", "")),
            qr_code=transacao.get("qr_code", ""),
            qr_code_base64=transacao.get("qr_code_base64", ""),
            ticket_url=transacao.get("ticket_url", "") or data.get("ticket_url", "") or "",
            expires_at=self._parse_datetime(data.get("date_of_expiration")) or expira,
        )

    def fetch_payment(self, provider_payment_id: str) -> dict:
        return self._request("GET", f"/v1/payments/{provider_payment_id}")

    def cancel_payment(self, provider_payment_id: str) -> dict:
        """Cancela a cobrança no provedor para que ela não possa mais ser paga."""
        return self._request(
            "PUT", f"/v1/payments/{provider_payment_id}", body={"status": "cancelled"}
        )

    # ── Webhook ─────────────────────────────────────────────────────────────

    def signature_is_valid(
        self, *, data_id: str, request_id: str, signature_header: str
    ) -> bool:
        """Confere o cabeçalho ``x-signature`` (ts=...,v1=...).

        Manifesto: ``id:{data.id};request-id:{x-request-id};ts:{ts};`` — partes
        sem valor saem do manifesto. Sem segredo configurado a notificação é
        recusada: aceitar sem conferir deixaria qualquer um liberar um corte.
        """
        if not self.webhook_secret:
            logger.warning("Webhook do Mercado Pago recebido sem MERCADOPAGO_WEBHOOK_SECRET.")
            return False

        partes = dict(
            p.split("=", 1) for p in signature_header.split(",") if "=" in p
        )
        ts, recebida = partes.get("ts", "").strip(), partes.get("v1", "").strip()
        if not ts or not recebida:
            return False

        pedacos = []
        if data_id:
            pedacos.append(f"id:{data_id.lower()};")
        if request_id:
            pedacos.append(f"request-id:{request_id};")
        pedacos.append(f"ts:{ts};")
        manifesto = "".join(pedacos)

        esperada = hmac.new(
            self.webhook_secret.encode(), manifesto.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(esperada, recebida)

    # ── Auxiliares ──────────────────────────────────────────────────────────

    @staticmethod
    def _parse_datetime(raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    @staticmethod
    def map_status(provider_status: str) -> str:
        return STATUS_MAP.get(provider_status, "pending")
