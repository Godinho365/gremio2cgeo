"""Tasks Celery do financeiro.

Uma vez por dia: garante a janela de mensalidades futuras, recalcula status
por data, consome crédito acumulado e desativa quem virou Sd/Cb.
"""
from __future__ import annotations

import logging

from celery import shared_task

from core.context import use_tenant
from core.models import Tenant

from .services import FinanceService

logger = logging.getLogger(__name__)


@shared_task(name="finance.roll_dues")
def roll_dues() -> int:
    total = 0
    for tenant in Tenant.objects.filter(is_active=True):
        try:
            with use_tenant(tenant.id):
                total += FinanceService().roll_all()
        except Exception:  # noqa: BLE001 - falha de um tenant não derruba os demais
            logger.exception("Falha ao rolar mensalidades do tenant %s", tenant.id)
    return total
