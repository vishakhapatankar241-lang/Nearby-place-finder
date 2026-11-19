# 📍 Nearby Places Finder

Full-stack app for the Geopulse Analytics take-home task: log in, then add / view / search places on a map.

**Stack:** React (Vite) + Leaflet + OpenStreetMap · Django + Django REST Framework + GeoDjango · PostgreSQL + PostGIS · JWT auth (bcrypt-hashed passwords)

## Quick start (Docker – recommended, works on Windows)

1. Install **Docker Desktop** and start it.
2. In this folder:
   ```bash
   copy .env.example .env        # Windows (cmd).  macOS/Linux: cp .env.example .env
   docker compose up --build
   ```
   First run takes a few minutes (downloads images, installs packages).
3. In a **second terminal**, load the sample data (creates the demo user too):
   ```bash
   docker compose exec backend python manage.py load_places data/sample_places.geojson
   ```
4. Open **http://localhost:5173** and log in:

   | | |
   |---|---|
   | Email | `demo@geopulse.test` |
   | Password | `Demo@12345` |

   Or click **Create an account** to sign up.

Backend API: http://localhost:8000/api/ · Django admin: http://localhost:8000/admin/

> `makemigrations` runs automatically on start and creates `accounts/migrations` and `places/migrations`. **Commit those files** to Git.

### Using the company's sample GeoJSON
Put their file in `backend/data/` and run:
```bash
docker compose exec backend python manage.py load_places data/<their_file>.geojson
```
The importer reads `name`, `category` (also `type`/`amenity`), `description`; rows with an unknown category or invalid coordinates are rejected and listed. A few synonyms (clinic → hospital, college → school, cafe → restaurant, store → shop) are mapped automatically (see `places/importers.py`).

### Admin user (optional feature)
```bash
docker compose exec backend python manage.py createsuperuser
```
Staff users can **view** all users' places (they can edit/delete only their own).

## Environment variables (`.env`)
See `.env.example`: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`, `VITE_API_URL`. No real secrets are committed; `.env` is git-ignored.

## Tests
```bash
docker compose exec backend python manage.py test places accounts -v 2
```
Covers: registration/login/bcrypt hashing, protected routes, ownership rules, validation, category filter, nearby, nearest, distance, polygon search, bulk import (GeoJSON + CSV).

## 10,000-point index test
```bash
docker compose exec backend python manage.py generate_points --count 10000
docker compose exec backend python manage.py benchmark_spatial --km 2
```
The command times a "within 2 km" query with and without the GiST index and prints `EXPLAIN ANALYZE`.
**Result on my machine:** _(paste your numbers here after running it)_

## API (all GeoJSON, all need `Authorization: Bearer <access token>`)

| Method | URL | Purpose |
|---|---|---|
| POST | `/api/auth/register/` | Sign up `{email, password}` → user + tokens |
| POST | `/api/auth/login/` | Log in → `access`, `refresh`, `user` |
| POST | `/api/auth/refresh/` | New access token |
| GET | `/api/auth/me/` | Current user |
| GET | `/api/places/?category=hospital,school` | FeatureCollection of my places |
| POST | `/api/places/` | Create (GeoJSON Feature, coordinates `[lng, lat]`) |
| GET/PUT/PATCH/DELETE | `/api/places/<id>/` | One place |
| GET | `/api/places/nearby/?lat=&lng=&radius_km=` | Within X km, sorted by distance (`ST_DWithin`) |
| GET | `/api/places/nearest/?lat=&lng=&n=` | N closest places |
| GET | `/api/places/<id>/distance/?lat=&lng=` | Metres from a point to the place |
| POST | `/api/places/within/` `{"polygon": <GeoJSON Polygon>}` | Places inside polygon (`ST_Intersects`) |
| POST | `/api/places/import/` (multipart `file`) | Bulk import GeoJSON/CSV |

## What I completed
- **Required:** sign up / log in / log out (JWT, bcrypt), protected routes, per-user data, Leaflet + OSM map, add place by clicking, markers + popups, edit, delete, category filter, GeoJSON REST API, validation + clear error messages (empty fields, bad coordinates, wrong login, API/network failures).
- **Spatial:** nearby search (radius slider), distance from browser location, polygon search, bulk import (GeoJSON/CSV, invalid rows rejected), marker clustering.
- **Extras:** admin role (view all), GiST spatial index + benchmark command, automated tests, Docker setup, nearest-N search.

## What I skipped
- Live deployment link and screen recording.
- Heatmap / routing.
- Editing a place's location by dragging its marker (coordinates can be edited in the form).

## What I would improve with more time
- Store JWT in an httpOnly cookie instead of localStorage (safer against XSS).
- Use PostGIS `<->` KNN index ordering for nearest-N on very large tables; paginate / load only markers in the current map bounds.
- Frontend tests (Vitest + React Testing Library) and CI.
- Rate-limit login, email verification, password reset.
- Production setup (gunicorn, nginx, HTTPS, collected static files).

## Running without Docker (advanced)
You need PostgreSQL with PostGIS and the GDAL/GEOS/PROJ libraries (on Windows this is the hard part – Docker avoids it). Then set `DB_HOST=localhost` in `.env`, `pip install -r backend/requirements.txt`, run `makemigrations`, `migrate`, `runserver` in `backend/`, and `npm install && npm run dev` in `frontend/`.
