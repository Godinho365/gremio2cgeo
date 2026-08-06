from __future__ import annotations

from rest_framework import serializers

from ..models import Acquisition, Asset, Category, FloorPlan, Location, Supplier


class TenantRelationsMixin:
    """Scopes relation fields to the current tenant (prevents cross-tenant FKs)."""

    tenant_scoped_fields: dict[str, type] = {}

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        for field_name, model in self.tenant_scoped_fields.items():
            field = self.fields.get(field_name)  # type: ignore[attr-defined]
            if field is not None:
                field.queryset = model.objects.for_current_tenant().alive()  # type: ignore[attr-defined]


class CategorySerializer(TenantRelationsMixin, serializers.ModelSerializer):
    tenant_scoped_fields = {"parent": Category}

    class Meta:
        model = Category
        fields = ["id", "name", "parent", "created_at"]
        read_only_fields = ["id", "created_at"]


class LocationSerializer(TenantRelationsMixin, serializers.ModelSerializer):
    tenant_scoped_fields = {"parent": Location}

    class Meta:
        model = Location
        fields = ["id", "name", "type", "parent", "created_at"]
        read_only_fields = ["id", "created_at"]


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
            "plan_x",
            "plan_y",
            "created_at",
        ]
        read_only_fields = ["id", "asset_tag", "status", "created_at"]


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
            "plan_x",
            "plan_y",
        ]


class FloorPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = FloorPlan
        fields = ["id", "name", "image_data", "updated_at"]
        read_only_fields = ["id", "updated_at"]


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
        ]
