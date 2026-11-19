import time

from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.core.management.base import BaseCommand
from django.db import connection

from places.models import Place


class Command(BaseCommand):
    help = "Time a 'within 2 km' query with and without the spatial (GiST) index."

    def add_arguments(self, parser):
        parser.add_argument("--km", type=float, default=2)
        parser.add_argument("--runs", type=int, default=10)

    def _time(self, qs, runs):
        qs.count()  # warm-up
        times = []
        for _ in range(runs):
            start = time.perf_counter()
            n = qs.count()
            times.append((time.perf_counter() - start) * 1000)
        return n, sum(times) / len(times)

    def handle(self, *args, **opts):
        point = Point(73.8567, 18.5204, srid=4326)  # central Pune
        qs = Place.objects.filter(location__dwithin=(point, D(km=opts["km"])))
        self.stdout.write(f"Total rows in table: {Place.objects.count()}")

        n, ms = self._time(qs, opts["runs"])
        self.stdout.write(self.style.SUCCESS(f"WITH index   : {n} rows within {opts['km']} km, avg {ms:.2f} ms"))

        with connection.cursor() as cur:
            cur.execute("SET enable_indexscan = off; SET enable_bitmapscan = off;")
        n, ms = self._time(qs, opts["runs"])
        self.stdout.write(self.style.WARNING(f"WITHOUT index: {n} rows within {opts['km']} km, avg {ms:.2f} ms"))
        with connection.cursor() as cur:
            cur.execute("RESET enable_indexscan; RESET enable_bitmapscan;")

        sql, params = qs.query.sql_with_params()
        with connection.cursor() as cur:
            cur.execute("EXPLAIN ANALYZE " + sql, params)
            self.stdout.write("\nQuery plan (look for 'Index Scan using ..._location_id'):")
            for (line,) in cur.fetchall():
                self.stdout.write("  " + line)
