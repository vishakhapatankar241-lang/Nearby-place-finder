import random

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from places.models import Place


class Command(BaseCommand):
    help = "Create N random places around Pune (for testing clustering and index speed)."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=10000)
        parser.add_argument("--email", default="demo@geopulse.test")
        parser.add_argument("--password", default="Demo@12345")

    def handle(self, *args, **opts):
        User = get_user_model()
        user = User.objects.filter(email=opts["email"]).first() or User.objects.create_user(
            opts["email"], opts["password"])
        cats = Place.Category.values
        batch, total = [], 0
        for i in range(opts["count"]):
            cat = random.choice(cats)
            lat, lng = random.uniform(18.40, 18.65), random.uniform(73.70, 74.00)
            batch.append(Place(owner=user, name=f"Random {cat} {i}", category=cat,
                               description="generated", location=Point(lng, lat, srid=4326)))
            if len(batch) == 2000:
                Place.objects.bulk_create(batch)
                total += len(batch)
                batch = []
        if batch:
            Place.objects.bulk_create(batch)
            total += len(batch)
        self.stdout.write(self.style.SUCCESS(f"Created {total} places for {user.email}."))
