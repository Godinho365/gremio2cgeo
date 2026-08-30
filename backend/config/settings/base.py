"""Base settings shared across environments."""
from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="unsafe-dev-secret")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "corsheaders",
    # local
    "core",
    "apps.accounts",
    "apps.assets",
    "apps.scheduling",
    "apps.custody",
    "apps.inventory",
    "apps.barbershop",
    "apps.payments",
    "apps.finance",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # resolves current tenant from the authenticated user / request
    "core.middleware.TenantMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://patrimonia:patrimonia@db:5432/patrimonia"),
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "core.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Patrimonia API",
    "DESCRIPTION": "ERP Patrimonial SaaS multi-tenant",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "AssetConditionEnum": "apps.assets.models.AssetCondition",
        "AssetStatusEnum": "apps.assets.models.AssetStatus",
        "BookingStatusEnum": "apps.scheduling.models.BookingStatus",
        "CustodyStatusEnum": "apps.custody.models.CustodyStatus",
        "InventoryStatusEnum": "apps.inventory.models.InventoryStatus",
        "AppointmentStatusEnum": "apps.barbershop.models.AppointmentStatus",
        "PaymentStatusEnum": "apps.payments.models.PaymentStatus",
        "DueStatusEnum": "apps.finance.models.DueStatus",
        "FinancialStatusEnum": "apps.finance.models.FinancialStatus",
    },
}

# --- Celery ---
CELERY_BROKER_URL = env("REDIS_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://redis:6379/0")
CELERY_TASK_TRACK_STARTED = True

# De quanto em quanto o servidor pergunta ao provedor se o Pix caiu.
PIX_SYNC_SECONDS = env.int("PIX_SYNC_SECONDS", default=60)

# Jobs periódicos (Celery beat).
CELERY_BEAT_SCHEDULE = {
    # RN-C4: marca cautelas vencidas como 'atrasada' de hora em hora.
    "mark-overdue-custodies": {
        "task": "custody.mark_overdue_custodies",
        "schedule": crontab(minute=0),
    },
    # RN-BB8: confirma o Pix e libera o horário mesmo com a tela fechada. É o
    # que substitui o webhook quando não há endereço público para recebê-lo.
    "sync-pending-payments": {
        "task": "payments.sync_pending_payments",
        "schedule": PIX_SYNC_SECONDS,
    },
    # RN-F1: janela de mensalidades, status por data, crédito, Sd/Cb — uma
    # vez por dia é suficiente (nenhum desses efeitos precisa ser imediato).
    "roll-finance-dues": {
        "task": "finance.roll_dues",
        "schedule": crontab(hour=1, minute=0),
    },
}

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:5173"])

# ── Pagamentos (Mercado Pago) ────────────────────────────────────────────────
# O access token e o segredo do webhook saem do painel do Mercado Pago em
# "Suas integrações". Sem token, o Pix fica desligado e o sistema avisa em vez
# de quebrar. Sem segredo, todo webhook é recusado — de propósito.
MERCADOPAGO_ACCESS_TOKEN = env("MERCADOPAGO_ACCESS_TOKEN", default="")
MERCADOPAGO_WEBHOOK_SECRET = env("MERCADOPAGO_WEBHOOK_SECRET", default="")
# URL pública deste backend para o Mercado Pago avisar. Vazio = só consulta ativa.
MERCADOPAGO_NOTIFICATION_URL = env("MERCADOPAGO_NOTIFICATION_URL", default="")
# Quanto tempo o Pix (e o horário que ele segura) vale.
PIX_EXPIRY_MINUTES = env.int("PIX_EXPIRY_MINUTES", default=15)
# Quanto custa o corte avulso. Use "1.00" para ensaiar a cobrança com dinheiro
# real sem gastar. O valor fica congelado em cada agendamento já feito.
WALK_IN_PRICE = env("WALK_IN_PRICE", default="15.00")
# Só para apontar a um ambiente de ensaio; vazio = API real do Mercado Pago.
MERCADOPAGO_API_BASE = env("MERCADOPAGO_API_BASE", default="")
# Valor único da mensalidade do grêmio (módulo Financeiro).
MEMBERSHIP_FEE = env("MEMBERSHIP_FEE", default="100.00")
# Planos do Financeiro (Fase 2) — cada um com seu valor mensal.
ASSOCIADO_FEE = env("ASSOCIADO_FEE", default="30.00")
BARBEARIA_FEE = env("BARBEARIA_FEE", default="20.00")
# Validade do link de convite pro plano Associado.
ASSOCIADO_INVITE_DAYS = env.int("ASSOCIADO_INVITE_DAYS", default=7)
