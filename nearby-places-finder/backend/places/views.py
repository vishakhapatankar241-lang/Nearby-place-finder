import json
import math

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import GEOSException, GEOSGeometry, Point
from django.contrib.gis.measure import D
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .importers import import_places, parse_csv, parse_geojson
from .models import Place
from .permissions import IsOwnerOrAdminReadOnly
from .serializers import PlaceSerializer

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_RADIUS_KM = 500
MAX_REJECTED_SHOWN = 100


def _number(request, name, minimum, maximum):
    raw = request.query_params.get(name)
    if raw in (None, ""):
        raise ValidationError({name: f"'{name}' is required."})
    try:
        value = float(raw)
    except ValueError:
        raise ValidationError({name: f"'{name}' must be a number."})
    if not math.isfinite(value) or not (minimum <= value <= maximum):
        raise ValidationError({name: f"'{name}' must be between {minimum} and {maximum}."})
    return value


def _point_from_query(request):
    lat = _number(request, "lat", -90, 90)
    lng = _number(request, "lng", -180, 180)
    return Point(lng, lat, srid=4326)


class PlaceViewSet(viewsets.ModelViewSet):
    """CRUD for places + spatial endpoints. All responses are GeoJSON."""

    serializer_class = PlaceSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdminReadOnly]
    pagination_class = None  

    def get_queryset(self):
        qs = Place.objects.select_related("owner")
        user = self.request.user
        if not user.is_staff:  
            qs = qs.filter(owner=user)
        raw = self.request.query_params.get("category")
        if raw:
            cats = [c.strip() for c in raw.split(",") if c.strip()]
            bad = [c for c in cats if c not in Place.Category.values]
            if bad:
                raise ValidationError({"category": f"Unknown category: {', '.join(bad)}."})
            qs = qs.filter(category__in=cats)
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    
    @action(detail=False, methods=["get"])
    def nearby(self, request):
        """GET /api/places/nearby/?lat=..&lng=..&radius_km=5  -> places within X km, closest first."""
        point = _point_from_query(request)
        radius = _number(request, "radius_km", 0.001, MAX_RADIUS_KM)
        qs = (
            self.get_queryset()
            .filter(location__dwithin=(point, D(km=radius)))  
            .annotate(distance=Distance("location", point))
            .order_by("distance")
        )
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def nearest(self, request):
        """GET /api/places/nearest/?lat=..&lng=..&n=5 -> the N closest places."""
        point = _point_from_query(request)
        n = int(_number(request, "n", 1, 100))
        qs = self.get_queryset().annotate(distance=Distance("location", point)).order_by("distance")[:n]
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["post"])
    def within(self, request):
        """POST /api/places/within/ {"polygon": <GeoJSON Polygon>} -> places inside the polygon."""
        geom_json = request.data.get("polygon")
        if isinstance(geom_json, dict) and geom_json.get("type") == "Feature":
            geom_json = geom_json.get("geometry")
        if not isinstance(geom_json, dict) or geom_json.get("type") != "Polygon":
            raise ValidationError({"polygon": "Send a GeoJSON Polygon in the 'polygon' field."})
        try:
            polygon = GEOSGeometry(json.dumps(geom_json), srid=4326)
        except (GEOSException, ValueError, TypeError):
            raise ValidationError({"polygon": "Invalid polygon (it must be a closed ring with at least 3 points)."})
        minx, miny, maxx, maxy = polygon.extent
        if not (-180 <= minx <= maxx <= 180 and -90 <= miny <= maxy <= 90):
            raise ValidationError({"polygon": "Polygon coordinates are outside valid longitude/latitude ranges."})
        if not polygon.valid:
            raise ValidationError({"polygon": "Polygon is invalid (edges cross each other)."})
        qs = self.get_queryset().filter(location__intersects=polygon)  
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def distance(self, request, pk=None):
        """GET /api/places/<id>/distance/?lat=..&lng=.. -> metres from the given point to this place."""
        place = self.get_object()
        point = _point_from_query(request)
        d = (Place.objects.filter(pk=place.pk)
             .annotate(distance=Distance("location", point))
             .values_list("distance", flat=True).first())
        metres = getattr(d, "m", d)
        return Response({"id": place.id, "distance_m": round(metres, 1), "distance_km": round(metres / 1000, 3)})

    @action(detail=False, methods=["post"], url_path="import", parser_classes=[MultiPartParser])
    def bulk_import(self, request):
        """POST /api/places/import/ (multipart, field 'file') with a .geojson/.json/.csv file."""
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "Attach a .geojson, .json or .csv file in the 'file' field."})
        if upload.size > MAX_UPLOAD_BYTES:
            raise ValidationError({"file": "File is too large (max 10 MB)."})
        filename = upload.name.lower()
        try:
            text = upload.read().decode("utf-8-sig")
            if filename.endswith((".geojson", ".json")):
                rows = parse_geojson(text)
            elif filename.endswith(".csv"):
                rows = parse_csv(text)
            else:
                raise ValidationError({"file": "Unsupported file type. Use .geojson, .json or .csv."})
            created, rejected = import_places(request.user, rows)
        except UnicodeDecodeError:
            raise ValidationError({"file": "File must be UTF-8 text."})
        except ValueError as exc:  # includes json.JSONDecodeError
            raise ValidationError({"file": f"Could not read the file: {exc}"})

        report = {"created": created, "rejected_count": len(rejected), "rejected": rejected[:MAX_REJECTED_SHOWN]}
        if created == 0:
            report["detail"] = "No rows were imported. Every row was rejected - see the reasons below."
            return Response(report, status=status.HTTP_400_BAD_REQUEST)
        return Response(report, status=status.HTTP_201_CREATED)
