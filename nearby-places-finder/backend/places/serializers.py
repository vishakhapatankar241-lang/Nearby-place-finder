from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .models import Place


class PlaceSerializer(GeoFeatureModelSerializer):
    """Outputs / accepts GeoJSON *Features*; a list becomes a GeoJSON FeatureCollection."""

    distance_m = serializers.SerializerMethodField()
    owner_email = serializers.CharField(source="owner.email", read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Place
        geo_field = "location"
        id_field = "id"
        fields = ("id", "name", "category", "description", "created_at",
                  "distance_m", "owner_email", "is_owner")

    def get_distance_m(self, obj):
        d = getattr(obj, "distance", None)  
        return round(d.m, 1) if d is not None else None

    def get_is_owner(self, obj):
        request = self.context.get("request")
        return bool(request and obj.owner_id == request.user.id)

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name cannot be empty.")
        return value

    def validate_description(self, value):
        return value.strip()

    def validate_location(self, point):
        if point.geom_type != "Point":
            raise serializers.ValidationError("Location must be a GeoJSON Point.")
        lng, lat = point.x, point.y
        if not (-180 <= lng <= 180):
            raise serializers.ValidationError(f"Longitude must be between -180 and 180 (got {lng}).")
        if not (-90 <= lat <= 90):
            raise serializers.ValidationError(f"Latitude must be between -90 and 90 (got {lat}).")
        point.srid = 4326
        return point
