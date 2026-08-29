"""FinanceService — mensalidades: geração, alocação de pagamento, status.

Scaffold desta Task 1 (só a classe, sem métodos): a lógica de negócio
(`activate_billing`, geração de janela, cálculo de status) é implementada na
Task 2 do plano
(docs/superpowers/plans/2026-08-29-modulo-financeiro-fase1.md). Existe aqui
porque `apps/finance/tests/test_finance.py` já importa `FinanceService` desde
o teste desta Task 1.
"""
from __future__ import annotations

from core.services import BaseService


class FinanceService(BaseService):
    """Scaffold — métodos chegam na Task 2 (ver docstring do módulo)."""
