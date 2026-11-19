from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from places.importers import import_places, parse_csv, parse_geojson


class Command(BaseCommand):
    help = "Seed the database from a GeoJSON/CSV file. Creates the owner user if needed."

    def add_arguments(self, parser):
        parser.add_argument("path", nargs="?", default="data/sample_places.geojson")
        parser.add_argument("--email", default="demo@geopulse.test")
        parser.add_argument("--password", default="Demo@12345")

    def handle(self, *args, **opts):
        path = Path(opts["path"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")
        User = get_user_model()
        user = User.objects.filter(email=opts["email"]).first()
        if user is None:
            user = User.objects.create_user(opts["email"], opts["password"])
            self.stdout.write(f"Created user {opts['email']} (password: {opts['password']})")
        text = path.read_text(encoding="utf-8-sig")
        rows = parse_csv(text) if path.suffix.lower() == ".csv" else parse_geojson(text)
        created, rejected = import_places(user, rows)
        self.stdout.write(self.style.SUCCESS(f"Imported {created} places, rejected {len(rejected)}."))
        for r in rejected[:20]:
            self.stdout.write(f"  row {r['row']}: {r['reason']}")
