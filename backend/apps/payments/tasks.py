"""Tasks Celery de pagamento.

Confirmação sem webhook: em vez de esperar o Mercado Pago avisar (o que exigiria
um endereço público chegando nesta máquina), o servidor pergunta de tempos em
tempos. É tráfego de saída, funciona atrás de qualquer firewall e não expõe
nada. Quando existe webhook configurado, os dois convivem — o que chegar
primeiro resolve, e reaplicar a mesma situação não muda nada.
"""
from __future__ import annotations

import logging

from celery import shared_task

from apps.barbershop.services import BarbershopService
from core.context import use_tenant

from .models import OPEN_PAYMENT_STATUSES, Payment
from .services import PaymentService

logger = logging.getLogger(__name__)


@shared_task(name="payments.sync_pending_payments")
def sync_pending_payments() -> int:
    """Confere no provedor toda cobrança ainda em aberto e reflete o resultado.

    Percorre os tenants sem filtro de contexto de propósito: é um job de fundo,
    não uma requisição de usuário. Cada cobrança é tratada dentro do tenant
    dela, e uma falha isolada não derruba as demais.
    """
    pagamentos = PaymentService()
    barbearia = BarbershopService(payments=pagamentos)
    tratadas = 0

    pendentes = Payment.objects.filter(status__in=OPEN_PAYMENT_STATUSES).order_by("created_at")
    for payment in pendentes.iterator():
        try:
            with use_tenant(payment.tenant_id):
                atualizado = pagamentos.sync(payment)
                barbearia.settle_appointment_for(atualizado)
            tratadas += 1
        except Exception:  # noqa: BLE001 - um pagamento ruim não pode parar a fila
            logger.exception("Falha ao sincronizar o pagamento %s", payment.pk)

    return tratadas
