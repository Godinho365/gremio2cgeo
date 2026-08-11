"""Pix ligado nos testes da barbearia, mas sem sair para a internet.

Só a camada HTTP do gateway é substituída — validação de payload, mapeamento
de situação e regras continuam sendo as de produção.
"""
from __future__ import annotations

import pytest

from apps.payments.gateways.mercadopago import MercadoPagoGateway

# Situação que a consulta ao provedor devolve. Os testes que precisam
# confirmar um pagamento trocam este valor.
PROVIDER_STATUS = {"value": "pending"}


@pytest.fixture(autouse=True)
def pix_configurado(request, settings, monkeypatch):
    """Liga o Pix e responde no lugar da API do Mercado Pago.

    Marque o teste com ``@pytest.mark.no_pix`` para exercitar a instalação
    sem credencial configurada.
    """
    PROVIDER_STATUS["value"] = "pending"
    # Preço fixo no teste: senão o resultado dependeria do WALK_IN_PRICE que o
    # operador deixou no .env da máquina.
    settings.WALK_IN_PRICE = "15.00"
    if request.node.get_closest_marker("no_pix"):
        settings.MERCADOPAGO_ACCESS_TOKEN = ""
        return

    settings.MERCADOPAGO_ACCESS_TOKEN = "TEST-token"
    settings.MERCADOPAGO_WEBHOOK_SECRET = "segredo-de-teste"
    contador = {"n": 0}

    def fake_request(self, method, path, *, body=None, headers=None):
        if method == "POST" and path == "/v1/payments":
            contador["n"] += 1
            assert headers and headers.get("X-Idempotency-Key"), "faltou chave de idempotência"
            assert body["payment_method_id"] == "pix"
            return {
                "id": f"MP-{contador['n']}",
                "status": "pending",
                "status_detail": "pending_waiting_transfer",
                "date_of_expiration": body["date_of_expiration"],
                "point_of_interaction": {
                    "transaction_data": {
                        "qr_code": "00020126580014br.gov.bcb.pix-copia-e-cola",
                        "qr_code_base64": "iVBORw0KGgoAAAANSUhEUg==",
                        "ticket_url": "https://mp.example/ticket",
                    }
                },
            }
        if method == "PUT" and path.startswith("/v1/payments/"):
            return {"id": path.rsplit("/", 1)[-1], "status": "cancelled"}
        if method == "GET" and path.startswith("/v1/payments/"):
            return {
                "id": path.rsplit("/", 1)[-1],
                "status": PROVIDER_STATUS["value"],
                "status_detail": "ok",
            }
        raise AssertionError(f"chamada inesperada ao provedor: {method} {path}")

    monkeypatch.setattr(MercadoPagoGateway, "_request", fake_request)
