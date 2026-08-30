from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.api.views import (
    MePasswordView,
    MeView,
    SignupView,
    TenantTokenView,
    UserViewSet,
)
from apps.assets.api.views import (
    AcquisitionViewSet,
    AssetViewSet,
    CategoryViewSet,
    LocationViewSet,
    SupplierViewSet,
)
from apps.barbershop.api.views import AppointmentViewSet, BarberViewSet
from apps.custody.api.views import CustodyViewSet
from apps.finance.api.views import (
    AssociadoInviteAcceptView,
    AssociadoInviteCandidatesView,
    AssociadoInviteListCreateView,
    BillingProfileViewSet,
    DueViewSet,
    FinanceDashboardView,
    FinancePixStatusView,
    InitiatePixPaymentView,
    MyFinanceView,
    SelfSubscribeView,
)
from apps.inventory.api.views import InventoryViewSet
from apps.payments.api.views import (
    CreditView,
    MercadoPagoWebhookView,
    PaymentConfigView,
)
from apps.scheduling.api.views import AvailabilityViewSet, BookingViewSet

app_name = "api"

router = DefaultRouter(trailing_slash=False)
router.register("users", UserViewSet, basename="user")
router.register("assets", AssetViewSet, basename="asset")
router.register("categories", CategoryViewSet, basename="category")
router.register("locations", LocationViewSet, basename="location")
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("acquisitions", AcquisitionViewSet, basename="acquisition")
router.register("availabilities", AvailabilityViewSet, basename="availability")
router.register("bookings", BookingViewSet, basename="booking")
router.register("custodies", CustodyViewSet, basename="custody")
router.register("inventories", InventoryViewSet, basename="inventory")
router.register("barbers", BarberViewSet, basename="barber")
router.register("appointments", AppointmentViewSet, basename="appointment")
router.register("billing-profiles", BillingProfileViewSet, basename="billingprofile")
router.register("dues", DueViewSet, basename="due")

urlpatterns = [
    path(
        "webhooks/mercadopago",
        MercadoPagoWebhookView.as_view(),
        name="mercadopago_webhook",
    ),
    path("payments/config", PaymentConfigView.as_view(), name="payments_config"),
    path("credits", CreditView.as_view(), name="credits"),
    path("finance/dashboard", FinanceDashboardView.as_view(), name="finance_dashboard"),
    path("finance/me", MyFinanceView.as_view(), name="finance_me"),
    path("finance/me/assinar", SelfSubscribeView.as_view(), name="finance_self_subscribe"),
    path("finance/me/pagar", InitiatePixPaymentView.as_view(), name="finance_initiate_pix"),
    path(
        "finance/me/pagamento/<str:payment_id>",
        FinancePixStatusView.as_view(),
        name="finance_pix_status",
    ),
    path(
        "finance/convites-associado",
        AssociadoInviteListCreateView.as_view(),
        name="associado_invites",
    ),
    path(
        "finance/convites-associado/candidatos",
        AssociadoInviteCandidatesView.as_view(),
        name="associado_invite_candidates",
    ),
    path(
        "finance/convites-associado/<str:token>/aceitar",
        AssociadoInviteAcceptView.as_view(),
        name="associado_invite_accept",
    ),
    path("auth/signup", SignupView.as_view(), name="signup"),
    path("auth/me", MeView.as_view(), name="me"),
    path("auth/me/password", MePasswordView.as_view(), name="me_password"),
    path("auth/token", TenantTokenView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    *router.urls,
]
