import io
import json

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from .models import Place

User = get_user_model()

SHANIWAR_WADA = (18.5195, 73.8553)
DECCAN = (18.5236, 73.8410)        # ~1.6 km from Shaniwar Wada
HINJEWADI = (18.5912, 73.7389)     # ~14 km away


def make_place(owner, name, latlng, category="shop"):
    return Place.objects.create(owner=owner, name=name, category=category,
                                location=Point(latlng[1], latlng[0], srid=4326))


def feature_body(name="Test", category="school", lat=18.52, lng=73.85, description="d"):
    return {"type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {"name": name, "category": category, "description": description}}


class AuthTests(APITestCase):
    def test_register_login_and_me(self):
        r = self.client.post("/api/auth/register/", {"email": "A@Test.com", "password": "Str0ng!Pass99"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIn("access", r.data)
        user = User.objects.get(email="a@test.com")
        self.assertNotEqual(user.password, "Str0ng!Pass99")        # hashed
        self.assertTrue(user.password.startswith("bcrypt_sha256"))  # bcrypt
        r = self.client.post("/api/auth/login/", {"email": "a@test.com", "password": "Str0ng!Pass99"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        self.assertEqual(self.client.get("/api/auth/me/").data["email"], "a@test.com")

    def test_wrong_password_rejected(self):
        User.objects.create_user("b@test.com", "Str0ng!Pass99")
        r = self.client.post("/api/auth/login/", {"email": "b@test.com", "password": "nope"}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_duplicate_and_weak_password(self):
        User.objects.create_user("c@test.com", "Str0ng!Pass99")
        r = self.client.post("/api/auth/register/", {"email": "c@test.com", "password": "Str0ng!Pass99"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/auth/register/", {"email": "d@test.com", "password": "12345678"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_places_require_login(self):
        self.assertEqual(self.client.get("/api/places/").status_code, 401)
        self.assertEqual(self.client.get("/api/places/nearby/?lat=18.5&lng=73.8&radius_km=2").status_code, 401)


class PlaceTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice@test.com", "Str0ng!Pass99")
        self.bob = User.objects.create_user("bob@test.com", "Str0ng!Pass99")
        self.client.force_authenticate(self.alice)

    def test_create_returns_geojson_and_list_is_featurecollection(self):
        r = self.client.post("/api/places/", feature_body(), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["type"], "Feature")
        self.assertEqual(r.data["geometry"]["type"], "Point")
        r = self.client.get("/api/places/")
        self.assertEqual(r.data["type"], "FeatureCollection")
        self.assertEqual(len(r.data["features"]), 1)

    def test_validation_errors(self):
        self.assertEqual(self.client.post("/api/places/", feature_body(name="   "), format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/places/", feature_body(category="zoo"), format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/places/", feature_body(lat=95), format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/places/", feature_body(lng=190), format="json").status_code, 400)

    def test_users_only_see_and_edit_own_places(self):
        mine = make_place(self.alice, "Mine", SHANIWAR_WADA)
        theirs = make_place(self.bob, "Theirs", DECCAN)
        names = [f["properties"]["name"] for f in self.client.get("/api/places/").data["features"]]
        self.assertEqual(names, ["Mine"])
        self.assertEqual(self.client.get(f"/api/places/{theirs.id}/").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/places/{theirs.id}/").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/places/{mine.id}/").status_code, 204)

    def test_admin_can_view_all_but_not_edit_others(self):
        admin = User.objects.create_user("admin@test.com", "Str0ng!Pass99", is_staff=True)
        place = make_place(self.bob, "Bob place", DECCAN)
        self.client.force_authenticate(admin)
        self.assertEqual(len(self.client.get("/api/places/").data["features"]), 1)
        self.assertEqual(self.client.delete(f"/api/places/{place.id}/").status_code, 403)

    def test_category_filter(self):
        make_place(self.alice, "H", SHANIWAR_WADA, "hospital")
        make_place(self.alice, "S", DECCAN, "school")
        r = self.client.get("/api/places/?category=hospital")
        self.assertEqual([f["properties"]["name"] for f in r.data["features"]], ["H"])
        self.assertEqual(self.client.get("/api/places/?category=zoo").status_code, 400)


class SpatialTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("s@test.com", "Str0ng!Pass99")
        self.client.force_authenticate(self.user)
        self.a = make_place(self.user, "Wada", SHANIWAR_WADA)
        self.b = make_place(self.user, "Deccan", DECCAN)
        self.c = make_place(self.user, "Hinjewadi", HINJEWADI)

    def test_nearby(self):
        r = self.client.get("/api/places/nearby/?lat=18.5195&lng=73.8553&radius_km=3")
        names = [f["properties"]["name"] for f in r.data["features"]]
        self.assertEqual(names, ["Wada", "Deccan"])  # sorted by distance, Hinjewadi excluded
        self.assertAlmostEqual(r.data["features"][1]["properties"]["distance_m"], 1600, delta=300)

    def test_nearby_bad_input(self):
        self.assertEqual(self.client.get("/api/places/nearby/?lat=abc&lng=73&radius_km=2").status_code, 400)
        self.assertEqual(self.client.get("/api/places/nearby/?lat=95&lng=73&radius_km=2").status_code, 400)
        self.assertEqual(self.client.get("/api/places/nearby/?lat=18&lng=73").status_code, 400)

    def test_nearest(self):
        r = self.client.get("/api/places/nearest/?lat=18.5195&lng=73.8553&n=2")
        self.assertEqual([f["properties"]["name"] for f in r.data["features"]], ["Wada", "Deccan"])

    def test_distance(self):
        r = self.client.get(f"/api/places/{self.b.id}/distance/?lat=18.5195&lng=73.8553")
        self.assertEqual(r.status_code, 200)
        self.assertAlmostEqual(r.data["distance_m"], 1600, delta=300)

    def test_polygon_search(self):
        poly = {"type": "Polygon", "coordinates": [[[73.83, 18.51], [73.87, 18.51], [73.87, 18.53],
                                                     [73.83, 18.53], [73.83, 18.51]]]}
        r = self.client.post("/api/places/within/", {"polygon": poly}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(sorted(f["properties"]["name"] for f in r.data["features"]), ["Deccan", "Wada"])

    def test_polygon_invalid(self):
        self.assertEqual(self.client.post("/api/places/within/", {"polygon": "x"}, format="json").status_code, 400)
        bad = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [0, 0]]]}
        self.assertEqual(self.client.post("/api/places/within/", {"polygon": bad}, format="json").status_code, 400)

    def test_bulk_import_geojson_rejects_bad_rows(self):
        Place.objects.all().delete()
        fc = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [73.85, 18.52]},
             "properties": {"name": "Good", "category": "school"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [73.85, 118.52]},
             "properties": {"name": "Bad lat", "category": "school"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [73.85, 18.52]},
             "properties": {"name": "", "category": "school"}},
        ]}
        f = SimpleUploadedFile("x.geojson", json.dumps(fc).encode(), content_type="application/json")
        r = self.client.post("/api/places/import/", {"file": f}, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["created"], 1)
        self.assertEqual(r.data["rejected_count"], 2)

    def test_bulk_import_csv(self):
        Place.objects.all().delete()
        csv_text = "name,category,description,latitude,longitude\nA,shop,x,18.5,73.8\nB,shop,x,200,73.8\n"
        f = SimpleUploadedFile("x.csv", csv_text.encode(), content_type="text/csv")
        r = self.client.post("/api/places/import/", {"file": f}, format="multipart")
        self.assertEqual(r.data["created"], 1)
        self.assertEqual(r.data["rejected"][0]["row"], 3)
