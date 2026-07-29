from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import AssetViewSet

router = DefaultRouter(trailing_slash=False)
router.register("", AssetViewSet, basename="asset")

urlpatterns = router.urls
