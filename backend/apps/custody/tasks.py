"""Tasks Celery do módulo de cautelas."""
from __future__ import annotations

from celery import shared_task

from .services import mark_overdue_custodies


@shared_task(name="custody.mark_overdue_custodies")
def mark_overdue_custodies_task() -> int:
    """RN-C4: marca cautelas ativas vencidas como 'atrasada'. Agendada no Celery beat."""
    return mark_overdue_custodies()
