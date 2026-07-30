from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.api.views import MeView, SignupView, TenantTokenView, UserViewSet
from apps.assets.api.views import (
    AcquisitionViewSet,
    AssetViewSet,
    CategoryViewSet,
    LocationViewSet,
    SupplierViewSet,
)
from apps.custody.api.views import CustodyViewSet
from apps.inventory.api.views import InventoryViewSet
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

urlpatterns = [
    path("auth/signup", SignupView.as_view(), name="signup"),
    path("auth/me", MeView.as_view(), name="me"),
    path("auth/token", TenantTokenView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    *router.urls,
]
