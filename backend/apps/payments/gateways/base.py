"""Contrato do provedor de pagamento. Trocar de provedor é trocar esta peça."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


class PaymentGatewayError(Exception):
    """Falha ao falar com o provedor (rede, credencial, resposta inesperada)."""

    def __init__(self, message: str, code: str = "gateway_error") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class PixCharge:
    """O que o provedor devolve ao abrir uma cobrança Pix."""

    provider_payment_id: str
    status: str
    status_detail: str
    qr_code: str
    qr_code_base64: str
    ticket_url: str
    expires_at: datetime | None


@dataclass(frozen=True)
class PayerInfo:
    email: str
    first_name: str
    last_name: str
    cpf: str


class PaymentGateway(Protocol):
    name: str

    def is_configured(self) -> bool: ...

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
    ) -> PixCharge: ...

    def fetch_payment(self, provider_payment_id: str) -> dict: ...

    def cancel_payment(self, provider_payment_id: str) -> dict: ...
