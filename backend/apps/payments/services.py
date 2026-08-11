"""PaymentService — abrir cobrança, conferir com o provedor e expirar (RN-P1..P3).

RN-P1  Cobrança nasce pendente e vale por PIX_EXPIRY_MINUTES.
RN-P2  Só o provedor diz que foi pago — nunca o cliente, nunca o corpo do webhook.
RN-P3  Cobrança vencida não vira paga; expira e libera o que estava segurando.
RN-P4  Desistiu depois de pagar? O valor não some nem é estornado: vira
       crédito no perfil (ver credits.py).
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from core import audit
from core.context import use_tenant
from core.exceptions import BusinessRuleError
from core.services import BaseService

from .gateways.base import PayerInfo, PaymentGatewayError
from .gateways.mercadopago import MercadoPagoGateway
from .models import Payment, PaymentStatus
from .repositories import PaymentRepository

logger = logging.getLogger(__name__)


class PaymentService(BaseService):
    def __init__(
        self, gateway: object | None = None, payments: PaymentRepository | None = None
    ) -> None:
        self.gateway = gateway or MercadoPagoGateway()
        self.payments = payments or PaymentRepository()

    def is_configured(self) -> bool:
        return bool(self.gateway.is_configured())

    # ── Abrir cobrança ──────────────────────────────────────────────────────

    def _payer_info(self, payer: User) -> PayerInfo:
        if not payer.email:
            raise BusinessRuleError(
                "Cadastre um e-mail no seu perfil para pagar por Pix.", code="payer_email_required"
            )
        nome = (payer.full_name or payer.display_name or payer.username).strip()
        primeiro, _, resto = nome.partition(" ")
        return PayerInfo(
            email=payer.email,
            first_name=primeiro or nome,
            last_name=resto or primeiro or nome,
            cpf=payer.cpf or "",
        )

    @transaction.atomic
    def open_pix_charge(
        self,
        *,
        amount: Decimal,
        description: str,
        payer: User,
        external_reference: str = "",
    ) -> Payment:
        if amount <= 0:
            raise BusinessRuleError("Valor da cobrança inválido.", code="invalid_amount")
        try:
            cobranca = self.gateway.create_pix_charge(
                amount=amount,
                description=description,
                payer=self._payer_info(payer),
                expires_in_minutes=settings.PIX_EXPIRY_MINUTES,
                idempotency_key=str(uuid.uuid4()),
                notification_url=settings.MERCADOPAGO_NOTIFICATION_URL or None,
                external_reference=external_reference,
            )
        except PaymentGatewayError as exc:
            raise BusinessRuleError(exc.message, code=exc.code) from exc

        payment = self.payments.create(
            provider=self.gateway.name,
            provider_payment_id=cobranca.provider_payment_id,
            amount=amount,
            description=description,
            payer_id=payer.pk,
            status=MercadoPagoGateway.map_status(cobranca.status),
            qr_code=cobranca.qr_code,
            qr_code_base64=cobranca.qr_code_base64,
            ticket_url=cobranca.ticket_url,
            expires_at=cobranca.expires_at,
            provider_status=cobranca.status,
            provider_status_detail=cobranca.status_detail,
            created_by_id=payer.pk,
        )
        audit.record(
            action="payment.opened",
            entity_type="Payment",
            entity_id=payment.id,
            actor_id=payer.pk,
            diff={"amount": str(amount), "provider_payment_id": cobranca.provider_payment_id},
        )
        return payment

    # ── Conferir com o provedor ─────────────────────────────────────────────

    @transaction.atomic
    def sync(self, payment: Payment) -> Payment:
        """Pergunta ao provedor em que pé está a cobrança (RN-P2)."""
        if payment.status != PaymentStatus.PENDING or not payment.provider_payment_id:
            return payment
        try:
            dados = self.gateway.fetch_payment(payment.provider_payment_id)
        except PaymentGatewayError as exc:
            logger.warning("Falha ao consultar pagamento %s: %s", payment.pk, exc.message)
            return self._expire_if_overdue(payment)
        return self._apply(payment, dados)

    def _apply(self, payment: Payment, dados: dict) -> Payment:
        bruto = str(dados.get("status", ""))
        novo = MercadoPagoGateway.map_status(bruto)
        payment.provider_status = bruto
        payment.provider_status_detail = str(dados.get("status_detail", ""))[:120]
        if novo != payment.status:
            payment.status = novo
            if novo == PaymentStatus.APPROVED:
                payment.paid_at = timezone.now()
            audit.record(
                action=f"payment.{novo}",
                entity_type="Payment",
                entity_id=payment.id,
                actor_id=payment.payer_id,
                diff={"provider_status": bruto},
            )
        payment.save(
            update_fields=[
                "status", "paid_at", "provider_status", "provider_status_detail", "updated_at"
            ]
        )
        return self._expire_if_overdue(payment)

    def _expire_if_overdue(self, payment: Payment) -> Payment:
        """RN-P3: passou do prazo sem pagar, a cobrança morre."""
        if payment.status != PaymentStatus.PENDING:
            return payment
        if payment.expires_at and payment.expires_at < timezone.now():
            payment.status = PaymentStatus.EXPIRED
            payment.save(update_fields=["status", "updated_at"])
            audit.record(
                action="payment.expired",
                entity_type="Payment",
                entity_id=payment.id,
                actor_id=payment.payer_id,
            )
        return payment

    @transaction.atomic
    def cancel(self, payment: Payment, *, actor_id=None) -> Payment:
        """Fecha a cobrança no provedor: depois disso ela não pode mais ser paga.

        Sem isto, quem desiste do horário e paga o Pix mesmo assim teria o
        dinheiro debitado sem nada em troca.
        """
        if payment.status != PaymentStatus.PENDING:
            return payment
        if payment.provider_payment_id:
            try:
                self.gateway.cancel_payment(payment.provider_payment_id)
            except PaymentGatewayError as exc:
                # Não trava o cancelamento do horário por causa do provedor: a
                # cobrança vence sozinha e o webhook corrige se algo cair.
                logger.warning(
                    "Não foi possível cancelar a cobrança %s: %s", payment.pk, exc.message
                )
        payment.status = PaymentStatus.CANCELLED
        payment.save(update_fields=["status", "updated_at"])
        audit.record(
            action="payment.cancelled",
            entity_type="Payment",
            entity_id=payment.id,
            actor_id=actor_id or payment.payer_id,
        )
        return payment

    def expire_overdue(self) -> list[Payment]:
        """Vence tudo que passou do prazo no tenant corrente."""
        vencidas = list(self.payments.overdue())
        for payment in vencidas:
            self._expire_if_overdue(payment)
        return vencidas

    # ── Webhook ─────────────────────────────────────────────────────────────

    def apply_provider_status(self, provider_payment_id: str) -> Payment | None:
        """Chamado pelo webhook: busca a cobrança e reconsulta o provedor.

        O corpo da notificação nunca é fonte de verdade — ele só diz *qual*
        cobrança olhar (RN-P2). O tenant vem da própria cobrança encontrada,
        já que a notificação chega sem contexto nenhum.
        """
        payment = self.payments.by_provider_id(provider_payment_id)
        if payment is None:
            logger.info("Webhook para cobrança desconhecida: %s", provider_payment_id)
            return None
        with use_tenant(payment.tenant_id):
            return self.sync(payment)
