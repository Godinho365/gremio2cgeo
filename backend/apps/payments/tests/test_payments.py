"""Pagamento por Pix: cobrança, confirmação, expiração e a assinatura do webhook.

Nenhum teste toca a rede: o provedor é substituído por um dublê que devolve o
mesmo formato de resposta documentado pelo Mercado Pago.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.services import OnboardingService
from apps.payments.gateways.base import PaymentGatewayError, PixCharge
from apps.payments.gateways.mercadopago import MercadoPagoGateway
from apps.payments.models import PaymentStatus
from apps.payments.services import PaymentService
from core.context import use_tenant
from core.exceptions import BusinessRuleError

pytestmark = pytest.mark.django_db

WEBHOOK_SECRET = "segredo-de-teste"


def _org(name: str):
    return OnboardingService().create_organization(
        org_name=name, admin_username=f"admin_{name}", admin_password="supersecret123"
    )


class FakeGateway:
    """Dublê do provedor. `next_status` controla o que a consulta responde."""

    name = "mercadopago"

    def __init__(self, *, configured: bool = True, fail: bool = False) -> None:
        self.configured = configured
        self.fail = fail
        self.next_status = "pending"
        self.created: list[dict] = []
        self.cancelled: list[str] = []
        self.idempotency_keys: list[str] = []

    def is_configured(self) -> bool:
        return self.configured

    def create_pix_charge(self, **kwargs) -> PixCharge:
        if self.fail:
            raise PaymentGatewayError("Mercado Pago fora do ar.", code="gateway_unavailable")
        self.created.append(kwargs)
        self.idempotency_keys.append(kwargs["idempotency_key"])
        return PixCharge(
            provider_payment_id=f"MP-{len(self.created)}",
            status="pending",
            status_detail="pending_waiting_transfer",
            qr_code="00020126580014br.gov.bcb.pix-copia-e-cola",
            qr_code_base64="iVBORw0KGgoAAAANSUhEUg==",
            ticket_url="https://mp.example/ticket",
            expires_at=timezone.now() + timedelta(minutes=kwargs["expires_in_minutes"]),
        )

    def fetch_payment(self, provider_payment_id: str) -> dict:
        return {"id": provider_payment_id, "status": self.next_status, "status_detail": "ok"}

    def cancel_payment(self, provider_payment_id: str) -> dict:
        self.cancelled.append(provider_payment_id)
        return {"id": provider_payment_id, "status": "cancelled"}


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _charge(tenant, payer, service: PaymentService):
    with use_tenant(tenant.id):
        return service.open_pix_charge(
            amount=Decimal("15.00"), description="Corte", payer=payer
        )


# ── Abrir cobrança ──────────────────────────────────────────────────────────


def test_opening_a_charge_stores_the_qr_code():
    tenant, admin = _org("pay1")
    admin.email = "cliente@example.com"
    admin.save(update_fields=["email"])
    service = PaymentService(gateway=FakeGateway())

    payment = _charge(tenant, admin, service)

    assert payment.status == PaymentStatus.PENDING
    assert payment.qr_code.startswith("00020126")
    assert payment.qr_code_base64
    assert payment.provider_payment_id == "MP-1"
    assert payment.expires_at > timezone.now()


def test_each_charge_gets_its_own_idempotency_key():
    """Chave repetida faria o Mercado Pago devolver a cobrança antiga."""
    tenant, admin = _org("pay2")
    admin.email = "c@example.com"
    admin.save(update_fields=["email"])
    gateway = FakeGateway()
    service = PaymentService(gateway=gateway)

    _charge(tenant, admin, service)
    _charge(tenant, admin, service)

    assert len(set(gateway.idempotency_keys)) == 2


def test_charge_requires_an_email():
    tenant, admin = _org("pay3")
    admin.email = ""
    admin.save(update_fields=["email"])
    service = PaymentService(gateway=FakeGateway())

    with pytest.raises(BusinessRuleError, match="e-mail"):
        _charge(tenant, admin, service)


def test_gateway_failure_becomes_a_business_error():
    tenant, admin = _org("pay4")
    admin.email = "c@example.com"
    admin.save(update_fields=["email"])
    service = PaymentService(gateway=FakeGateway(fail=True))

    with pytest.raises(BusinessRuleError) as exc:
        _charge(tenant, admin, service)
    assert exc.value.code == "gateway_unavailable"


def test_cpf_goes_along_when_the_person_has_one():
    tenant, admin = _org("pay5")
    admin.email = "c@example.com"
    admin.cpf = "12345678909"
    admin.full_name = "João da Silva"
    admin.save(update_fields=["email", "cpf", "full_name"])
    gateway = FakeGateway()

    _charge(tenant, admin, PaymentService(gateway=gateway))

    payer = gateway.created[0]["payer"]
    assert payer.cpf == "12345678909"
    assert payer.first_name == "João"
    assert payer.last_name == "da Silva"


# ── Confirmar e expirar ─────────────────────────────────────────────────────


def test_sync_marks_the_charge_as_paid():
    tenant, admin = _org("pay6")
    admin.email = "c@example.com"
    admin.save(update_fields=["email"])
    gateway = FakeGateway()
    service = PaymentService(gateway=gateway)
    payment = _charge(tenant, admin, service)

    gateway.next_status = "approved"
    with use_tenant(tenant.id):
        atualizado = service.sync(payment)

    assert atualizado.status == PaymentStatus.APPROVED
    assert atualizado.paid_at is not None


def test_a_charge_past_its_deadline_expires():
    tenant, admin = _org("pay7")
    admin.email = "c@example.com"
    admin.save(update_fields=["email"])
    gateway = FakeGateway()
    service = PaymentService(gateway=gateway)
    payment = _charge(tenant, admin, service)

    payment.expires_at = timezone.now() - timedelta(minutes=1)
    payment.save(update_fields=["expires_at"])

    with use_tenant(tenant.id):
        assert service.sync(payment).status == PaymentStatus.EXPIRED


def test_the_provider_decides_not_the_caller():
    """Provedor ainda pendente: a cobrança não vira paga por conta própria."""
    tenant, admin = _org("pay8")
    admin.email = "c@example.com"
    admin.save(update_fields=["email"])
    gateway = FakeGateway()
    service = PaymentService(gateway=gateway)
    payment = _charge(tenant, admin, service)

    with use_tenant(tenant.id):
        assert service.sync(payment).status == PaymentStatus.PENDING


# ── Assinatura do webhook ───────────────────────────────────────────────────


def _signature(data_id: str, request_id: str, ts: str, secret: str = WEBHOOK_SECRET) -> str:
    manifesto = f"id:{data_id};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(secret.encode(), manifesto.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


def test_signature_accepts_a_genuine_notification():
    gateway = MercadoPagoGateway(access_token="x", webhook_secret=WEBHOOK_SECRET)
    assert gateway.signature_is_valid(
        data_id="123", request_id="req-1", signature_header=_signature("123", "req-1", "1700000000")
    )


def test_signature_rejects_a_forged_one():
    gateway = MercadoPagoGateway(access_token="x", webhook_secret=WEBHOOK_SECRET)
    assert not gateway.signature_is_valid(
        data_id="123",
        request_id="req-1",
        signature_header=_signature("123", "req-1", "1700000000", secret="outro-segredo"),
    )
    # Trocar o id depois de assinar também não passa.
    assert not gateway.signature_is_valid(
        data_id="999", request_id="req-1", signature_header=_signature("123", "req-1", "1700000000")
    )


def test_without_a_configured_secret_everything_is_rejected():
    """Sem segredo, aceitar o webhook deixaria qualquer um liberar um corte."""
    gateway = MercadoPagoGateway(access_token="x", webhook_secret="")
    assert not gateway.signature_is_valid(
        data_id="123", request_id="req-1", signature_header=_signature("123", "req-1", "1700000000")
    )


def test_malformed_signature_header_is_rejected():
    gateway = MercadoPagoGateway(access_token="x", webhook_secret=WEBHOOK_SECRET)
    for header in ("", "lixo", "ts=123", "v1=abc"):
        assert not gateway.signature_is_valid(
            data_id="123", request_id="req-1", signature_header=header
        )


def test_webhook_endpoint_refuses_an_unsigned_notification(client: APIClient, settings):
    settings.MERCADOPAGO_WEBHOOK_SECRET = WEBHOOK_SECRET
    resposta = client.post(
        "/api/webhooks/mercadopago",
        data=json.dumps({"type": "payment", "data": {"id": "123"}}),
        content_type="application/json",
    )
    assert resposta.status_code == 401
    assert resposta.data["error"]["code"] == "invalid_signature"


def test_gateway_not_configured_is_reported_clearly():
    gateway = MercadoPagoGateway(access_token="", webhook_secret="")
    assert gateway.is_configured() is False
    with pytest.raises(PaymentGatewayError) as exc:
        gateway.fetch_payment("1")
    assert exc.value.code == "payments_not_configured"


def test_cancelling_closes_the_charge_at_the_provider():
    """Desistiu: a cobrança é fechada para ninguém pagar um horário que não existe."""
    tenant, admin = _org("pay9")
    admin.email = "c@example.com"
    admin.save(update_fields=["email"])
    gateway = FakeGateway()
    service = PaymentService(gateway=gateway)
    payment = _charge(tenant, admin, service)

    with use_tenant(tenant.id):
        cancelada = service.cancel(payment)

    assert cancelada.status == PaymentStatus.CANCELLED
    assert gateway.cancelled == [payment.provider_payment_id]


def test_cancelling_survives_a_provider_outage():
    """Provedor fora do ar não pode impedir a pessoa de desistir do horário."""
    tenant, admin = _org("pay10")
    admin.email = "c@example.com"
    admin.save(update_fields=["email"])
    gateway = FakeGateway()
    service = PaymentService(gateway=gateway)
    payment = _charge(tenant, admin, service)

    def explode(_):
        raise PaymentGatewayError("fora do ar", code="gateway_unavailable")

    gateway.cancel_payment = explode
    with use_tenant(tenant.id):
        assert service.cancel(payment).status == PaymentStatus.CANCELLED


# ── Confirmação de fundo (sem webhook) ──────────────────────────────────────


def test_background_task_confirms_without_any_webhook(settings, monkeypatch):
    """O servidor pergunta ao provedor; nada precisa chegar de fora."""
    from apps.barbershop.models import AppointmentStatus
    from apps.payments.tasks import sync_pending_payments

    tenant, admin = _org("pay11")
    admin.email = "c@example.com"
    admin.save(update_fields=["email"])
    gateway = FakeGateway()
    service = PaymentService(gateway=gateway)
    payment = _charge(tenant, admin, service)

    # A task monta os próprios serviços; aponta os dois para o mesmo dublê.
    monkeypatch.setattr("apps.payments.tasks.PaymentService", lambda: service)
    gateway.next_status = "approved"

    from apps.barbershop.models import Appointment, Barber
    from apps.barbershop.repositories import AppointmentRepository
    from apps.barbershop.services import BarbershopService

    with use_tenant(tenant.id):
        barber = Barber.objects.create(tenant_id=tenant.id, name="Zé")
        inicio = timezone.now() + timedelta(days=1)
        ag = AppointmentRepository().create(
            barber_id=barber.id, customer_id=admin.pk,
            start_at=inicio, end_at=inicio + timedelta(minutes=30),
            is_subscriber=False, price=Decimal("15.00"), payment=payment,
            status=AppointmentStatus.AWAITING_PAYMENT,
        )
    monkeypatch.setattr(
        "apps.payments.tasks.BarbershopService",
        lambda payments=None: BarbershopService(payments=service),
    )

    assert sync_pending_payments() == 1

    payment.refresh_from_db()
    ag.refresh_from_db()
    assert payment.status == PaymentStatus.APPROVED
    assert ag.status == AppointmentStatus.SCHEDULED
    assert Appointment.objects.filter(pk=ag.pk, status="scheduled").exists()


def test_background_task_survives_one_bad_payment(monkeypatch):
    """Uma cobrança problemática não pode travar a fila das outras."""
    from apps.payments.tasks import sync_pending_payments

    tenant, admin = _org("pay12")
    admin.email = "c@example.com"
    admin.save(update_fields=["email"])
    gateway = FakeGateway()
    service = PaymentService(gateway=gateway)
    primeira = _charge(tenant, admin, service)
    _charge(tenant, admin, service)

    original = service.sync

    def explode(payment):
        if payment.pk == primeira.pk:
            raise RuntimeError("provedor devolveu lixo")
        return original(payment)

    service.sync = explode
    monkeypatch.setattr("apps.payments.tasks.PaymentService", lambda: service)

    # A segunda é tratada mesmo com a primeira estourando.
    assert sync_pending_payments() == 1


# ── Recados do provedor em português ────────────────────────────────────────


@pytest.mark.parametrize(
    ("mensagem_mp", "trecho_esperado"),
    [
        ("Unauthorized use of live credentials", "mesmo tipo"),
        ("One of the parties is a test user", "de teste e a outra é real"),
        ("Invalid payment_method_id", "não está habilitado"),
        ("Invalid users involved", "paga a si mesmo"),
    ],
)
def test_opaque_provider_errors_get_explained(mensagem_mp, trecho_esperado):
    """A mensagem crua do Mercado Pago não diz o que fazer; a nossa diz."""
    import io
    import json as _json
    import urllib.error

    erro = urllib.error.HTTPError(
        url="https://api.mercadopago.com/v1/payments",
        code=400,
        msg="Bad Request",
        hdrs=None,
        fp=io.BytesIO(_json.dumps({"message": mensagem_mp}).encode()),
    )
    explicado = MercadoPagoGateway._error_detail(erro)
    assert trecho_esperado in explicado
    # O texto original continua junto — é o que o suporte deles pede.
    assert mensagem_mp in explicado


def test_unknown_provider_errors_pass_through():
    import io
    import json as _json
    import urllib.error

    erro = urllib.error.HTTPError(
        url="x", code=400, msg="Bad Request", hdrs=None,
        fp=io.BytesIO(_json.dumps({"message": "Something new happened"}).encode()),
    )
    assert MercadoPagoGateway._error_detail(erro) == "Something new happened"
