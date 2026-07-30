"""Cria dados de demonstração: organização + usuários (admin e comum) + bens.

Uso: python manage.py seed_demo
Idempotente: se o usuário 'demo' já existir, não faz nada.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.accounts.models import RoleCode, User
from apps.accounts.services import OnboardingService, UserService
from apps.assets.services import AssetService
from apps.scheduling.models import Availability, Weekday
from core.context import use_tenant

ADMIN = ("demo", "demo12345")
NORMAL = ("usuario", "usuario12345")


class Command(BaseCommand):
    help = "Cria dados de demonstração (org, usuário admin e comum, bens e disponibilidade)."

    def handle(self, *args: object, **options: object) -> None:
        if User.objects.filter(username=ADMIN[0]).exists():
            self.stdout.write("Demo já existe — nada a fazer.")
            self._print_credentials()
            return

        tenant, _admin = OnboardingService().create_organization(
            org_name="Demo Org",
            admin_username=ADMIN[0],
            admin_password=ADMIN[1],
            admin_email="demo@exemplo.com",
        )
        with use_tenant(tenant.id):
            UserService().create_user(
                username=NORMAL[0],
                password=NORMAL[1],
                email="usuario@exemplo.com",
                role_codes=[RoleCode.USER],
                tenant_id=tenant.id,
            )
            assets = AssetService()
            notebook = assets.create_asset(name="Notebook Dell Latitude")
            assets.create_asset(name="Projetor Epson")
            assets.create_asset(name="Cadeira de Escritório")
            for weekday in (
                Weekday.MONDAY,
                Weekday.TUESDAY,
                Weekday.WEDNESDAY,
                Weekday.THURSDAY,
                Weekday.FRIDAY,
            ):
                Availability.objects.create(
                    tenant_id=tenant.id,
                    asset=notebook,
                    weekday=weekday,
                    start_time="00:00",
                    end_time="23:59",
                )

        self.stdout.write(self.style.SUCCESS("Dados de demonstração criados."))
        self._print_credentials()

    def _print_credentials(self) -> None:
        self.stdout.write("")
        self.stdout.write(f"  Admin:   {ADMIN[0]} / {ADMIN[1]}")
        self.stdout.write(f"  Usuário: {NORMAL[0]} / {NORMAL[1]}")
