"""Bulk import helpers (GeoJSON + CSV). Rows with invalid data are rejected, valid ones are saved."""
import csv
import io
import json
import math

from django.contrib.gis.geos import Point

from .models import Place

NAME_KEYS = ("name", "title", "place", "place_name")
CATEGORY_KEYS = ("category", "type", "amenity", "kind")
DESC_KEYS = ("description", "desc", "details", "address")
LAT_KEYS = ("latitude", "lat", "y")
LNG_KEYS = ("longitude", "lng", "lon", "long", "x")


ALIASES = {
    "clinic": "hospital", "medical": "hospital", "pharmacy": "hospital", "health": "hospital",
    "college": "school", "university": "school", "education": "school",
    "cafe": "restaurant", "hotel": "restaurant", "food": "restaurant", "bakery": "restaurant",
    "store": "shop", "mall": "shop", "market": "shop", "supermarket": "shop", "retail": "shop",
}


def _first(d, keys):
    lowered = {str(k).strip().lower(): v for k, v in d.items()}
    for key in keys:
        value = lowered.get(key)
        if value not in (None, ""):
            return value
    return None


def _to_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_geojson(text):
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("GeoJSON must be an object.")
    if data.get("type") == "FeatureCollection":
        features = data.get("features")
    elif data.get("type") == "Feature":
        features = [data]
    else:
        raise ValueError("GeoJSON must be a FeatureCollection or a Feature.")
    if not isinstance(features, list):
        raise ValueError("FeatureCollection has no 'features' list.")
    for i, feature in enumerate(features, start=1):
        feature = feature if isinstance(feature, dict) else {}
        geom = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
        props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
        coords = geom.get("coordinates") if geom.get("type") == "Point" else None
        ok = isinstance(coords, (list, tuple)) and len(coords) >= 2
        yield i, {
            "name": _first(props, NAME_KEYS),
            "category": _first(props, CATEGORY_KEYS),
            "description": _first(props, DESC_KEYS) or "",
            "lng": coords[0] if ok else None,  
            "lat": coords[1] if ok else None,
            "error": None if ok else "Geometry must be a Point with coordinates [lng, lat].",
        }


def parse_csv(text):
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV file is empty.")
    for i, row in enumerate(reader, start=2):  
        yield i, {
            "name": _first(row, NAME_KEYS),
            "category": _first(row, CATEGORY_KEYS),
            "description": _first(row, DESC_KEYS) or "",
            "lat": _first(row, LAT_KEYS),
            "lng": _first(row, LNG_KEYS),
            "error": None,
        }


def clean_row(raw):
    """Return (data, None) if valid, or (None, 'reason') if the row must be rejected."""
    if raw.get("error"):
        return None, raw["error"]
    name = str(raw.get("name") or "").strip()
    if not name:
        return None, "Name is empty."
    if len(name) > 120:
        return None, "Name is longer than 120 characters."
    category = str(raw.get("category") or "").strip().lower()
    category = ALIASES.get(category, category)
    if category not in Place.Category.values:
        return None, f"Unknown category '{raw.get('category')}'. Use: {', '.join(Place.Category.values)}."
    lat, lng = _to_float(raw.get("lat")), _to_float(raw.get("lng"))
    if lat is None or lng is None:
        return None, "Latitude/longitude missing or not a number."
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return None, f"Invalid coordinates (lat={lat}, lng={lng})."
    return {
        "name": name,
        "category": category,
        "description": str(raw.get("description") or "").strip(),
        "location": Point(lng, lat, srid=4326),
    }, None


def import_places(owner, rows, batch_size=1000):
    """Save valid rows (in batches), collect rejected ones. Returns (created_count, rejected_list)."""
    created, rejected, buffer = 0, [], []
    for row_number, raw in rows:
        data, error = clean_row(raw)
        if error:
            rejected.append({"row": row_number, "reason": error})
            continue
        buffer.append(Place(owner=owner, **data))
        if len(buffer) >= batch_size:
            Place.objects.bulk_create(buffer)
            created += len(buffer)
            buffer = []
    if buffer:
        Place.objects.bulk_create(buffer)
        created += len(buffer)
    return created, rejected
