"""Diagnóstico do Pix: diz por que a cobrança vai (ou não vai) funcionar.

Só faz leitura na API do Mercado Pago — não cria cobrança e não move dinheiro.

    python manage.py pix_check
"""
from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.barbershop.models import walk_in_price
from apps.payments.gateways.base import PaymentGatewayError
from apps.payments.gateways.mercadopago import MercadoPagoGateway


class Command(BaseCommand):
    help = "Confere se o Pix está pronto para cobrar (apenas leitura)."

    def handle(self, *args: object, **options: object) -> None:
        ok = self.style.SUCCESS
        erro = self.style.ERROR
        aviso = self.style.WARNING

        if not settings.MERCADOPAGO_ACCESS_TOKEN:
            self.stdout.write(erro("✗ Sem MERCADOPAGO_ACCESS_TOKEN."))
            self.stdout.write(
                "  Coloque o token em backend/.env e recrie o container:\n"
                "    docker compose up -d --force-recreate backend celery-worker celery-beat\n"
                "  Atenção: 'docker compose restart' NÃO relê o .env."
            )
            return

        gateway = MercadoPagoGateway()
        try:
            conta = gateway._request("GET", "/users/me")
            metodos = gateway._request("GET", "/v1/payment_methods")
        except PaymentGatewayError as exc:
            self.stdout.write(erro(f"✗ O Mercado Pago recusou a credencial: {exc.message}"))
            return

        tags = conta.get("tags") or []
        eh_teste = "test_user" in tags
        tem_pix = any(m.get("id") == "pix" for m in metodos)

        self.stdout.write("Conta que vai receber:")
        self.stdout.write(f"  e-mail   {conta.get('email')}")
        self.stdout.write(f"  apelido  {conta.get('nickname')}")
        self.stdout.write("")

        if eh_teste:
            self.stdout.write(erro("✗ É uma conta de TESTE do Mercado Pago."))
            self.stdout.write(
                "  Conta de teste só cobra de pagador de teste. Como quem marca no\n"
                "  sistema usa e-mail real, toda cobrança é recusada com\n"
                "  'Unauthorized use of live credentials'.\n"
                "  → Pegue o token na aplicação da conta REAL do grêmio."
            )
        else:
            self.stdout.write(ok("✓ Conta real (não é usuário de teste)."))

        if tem_pix:
            self.stdout.write(ok("✓ Pix habilitado nesta conta."))
        else:
            self.stdout.write(erro("✗ Pix NÃO habilitado nesta conta."))
            self.stdout.write(
                "  Cadastre uma chave Pix no aplicativo do Mercado Pago\n"
                "  (Área Pix → Gerenciar chaves → Cadastrar chave; a aleatória serve)\n"
                "  e conclua a validação da conta, se houver pendência."
            )

        self.stdout.write("")
        if not eh_teste and tem_pix:
            self.stdout.write(ok("Tudo pronto: o corte avulso já pode ser cobrado por Pix."))
            self.stdout.write(
                aviso(
                    f"Lembre que é dinheiro real: R$ {walk_in_price():.2f} por corte "
                    f"(WALK_IN_PRICE no .env), com {settings.PIX_EXPIRY_MINUTES} min "
                    "para pagar. Cobrança não paga expira sozinha, sem custo."
                )
            )
        else:
            self.stdout.write(erro("Ainda não dá para cobrar. Resolva os itens marcados com ✗."))
