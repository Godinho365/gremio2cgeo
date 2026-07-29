from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.api.views import MeView, SignupView, TenantTokenView, UserViewSet
from apps.assets.api.views import AssetViewSet

app_name = "api"

router = DefaultRouter(trailing_slash=False)
router.register("users", UserViewSet, basename="user")
router.register("assets", AssetViewSet, basename="asset")

urlpatterns = [
    path("auth/signup", SignupView.as_view(), name="signup"),
    path("auth/me", MeView.as_view(), name="me"),
    path("auth/token", TenantTokenView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    *router.urls,
]
