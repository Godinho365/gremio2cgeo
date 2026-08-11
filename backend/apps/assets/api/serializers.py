from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from apps.custody.models import OPEN_CUSTODY_STATUSES
from apps.scheduling.models import BookingStatus

from ..models import Acquisition, Asset, Category, Location, Supplier


class TenantRelationsMixin:
    """Scopes relation fields to the current tenant (prevents cross-tenant FKs)."""

    tenant_scoped_fields: dict[str, type] = {}

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        for field_name, model in self.tenant_scoped_fields.items():
            field = self.fields.get(field_name)  # type: ignore[attr-defined]
            if field is not None:
                field.queryset = model.objects.for_current_tenant().alive()  # type: ignore[attr-defined]


class AssetCountMixin:
    """Quantos bens usam este registro — a tela precisa saber antes de excluir."""

    def get_asset_count(self, obj: object) -> int:
        annotated = getattr(obj, "asset_count", None)
        if annotated is not None:
            return int(annotated)
        return obj.assets.filter(deleted_at__isnull=True).count()  # type: ignore[attr-defined]


class CategorySerializer(AssetCountMixin, TenantRelationsMixin, serializers.ModelSerializer):
    tenant_scoped_fields = {"parent": Category}
    asset_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "parent", "asset_count", "created_at"]
        read_only_fields = ["id", "asset_count", "created_at"]


class LocationSerializer(AssetCountMixin, TenantRelationsMixin, serializers.ModelSerializer):
    tenant_scoped_fields = {"parent": Location}
    asset_count = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = ["id", "name", "type", "parent", "asset_count", "created_at"]
        read_only_fields = ["id", "asset_count", "created_at"]


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "name", "document", "email", "created_at"]
        read_only_fields = ["id", "created_at"]


class AcquisitionSerializer(TenantRelationsMixin, serializers.ModelSerializer):
    tenant_scoped_fields = {"supplier": Supplier}

    class Meta:
        model = Acquisition
        fields = ["id", "type", "supplier", "document_ref", "date", "value", "created_at"]
        read_only_fields = ["id", "created_at"]


class AssetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    location_name = serializers.CharField(source="location.name", read_only=True, default=None)
    has_open_custody = serializers.SerializerMethodField()
    is_reserved_now = serializers.SerializerMethodField()
    has_upcoming_booking = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
            "id",
            "asset_tag",
            "name",
            "description",
            "category",
            "category_name",
            "location",
            "location_name",
            "acquisition",
            "status",
            "condition",
            "acquisition_value",
            "protection_notes",
            "is_bookable",
            "photo_data",
            "has_open_custody",
            "is_reserved_now",
            "has_upcoming_booking",
            "created_at",
        ]
        read_only_fields = ["id", "asset_tag", "status", "created_at"]

    def get_has_open_custody(self, obj: Asset) -> bool:
        """Anotado pela listagem; nas demais respostas cai na consulta direta."""
        annotated = getattr(obj, "has_open_custody", None)
        if annotated is not None:
            return bool(annotated)
        return obj.custodies.filter(
            status__in=OPEN_CUSTODY_STATUSES, deleted_at__isnull=True
        ).exists()

    def get_is_reserved_now(self, obj: Asset) -> bool:
        """Reserva aprovada cobrindo este momento — o bem já está com a pessoa."""
        annotated = getattr(obj, "is_reserved_now", None)
        if annotated is not None:
            return bool(annotated)
        now = timezone.now()
        return self._approved(obj).filter(start_at__lte=now, end_at__gt=now).exists()

    def get_has_upcoming_booking(self, obj: Asset) -> bool:
        """Reserva aprovada que ainda vai começar."""
        annotated = getattr(obj, "has_upcoming_booking", None)
        if annotated is not None:
            return bool(annotated)
        return self._approved(obj).filter(start_at__gt=timezone.now()).exists()

    @staticmethod
    def _approved(obj: Asset):
        return obj.bookings.filter(status=BookingStatus.APPROVED, deleted_at__isnull=True)


class AssetUpdateSerializer(TenantRelationsMixin, serializers.ModelSerializer):
    """Edição do bem — permite alterar a situação (status). asset_tag é imutável (RN-A1)."""

    tenant_scoped_fields = {
        "category": Category,
        "location": Location,
        "acquisition": Acquisition,
    }

    class Meta:
        model = Asset
        fields = [
            "name",
            "description",
            "category",
            "location",
            "acquisition",
            "status",
            "condition",
            "acquisition_value",
            "protection_notes",
            "is_bookable",
            "photo_data",
        ]


class AssetCreateSerializer(TenantRelationsMixin, serializers.ModelSerializer):
    # asset_tag optional: auto-generated (PAT-year-seq) when blank.
    asset_tag = serializers.CharField(required=False, allow_blank=True)
    tenant_scoped_fields = {
        "category": Category,
        "location": Location,
        "acquisition": Acquisition,
    }

    class Meta:
        model = Asset
        fields = [
            "asset_tag",
            "name",
            "description",
            "category",
            "location",
            "acquisition",
            "condition",
            "acquisition_value",
            "protection_notes",
            "is_bookable",
            "photo_data",
        ]
