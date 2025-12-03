# Real-Time Public Transport Tracking for Small Cities

A lightweight GPS tracking server and web UI designed for small-city bus fleets and pilot deployments. The app accepts OwnTracks-friendly location posts, stores them in a CSV log (simple default), and exposes APIs and a Leaflet web interface for live vehicle monitoring.

**Status:** Prototype / demo. Suitable for local testing and small pilots. See **Security** before exposing publicly.

## Repository Structure

- `app.py` — Flask server and HTTP API endpoints.
- `bus.csv` — append-only CSV log of received location messages (created by `app.py`).
- `stops.csv` — bus stops CSV used by the UI and `/api/stops` endpoint.
- `routes.json` — example route geometries for visualization.
- `static/` — frontend UI (Leaflet map, JS and CSS). The main UI is in `static/index.html`.
- `requirements.txt` — Python dependencies.

## Features

- OwnTracks-friendly `POST /location` ingest endpoint.
- APIs to fetch the latest vehicle locations, routes and stops.
- Server-Sent Events (`/api/stream`) to push location changes to the UI.
- Simple CSV-backed store for quick setup and reproducible demos.
- Rich client UI using Leaflet: live markers, trails, stops, arrival estimates and filters.

## Quick Start (local)

Requirements:
- Python 3.10+ (3.11 recommended)
- `pip` and `venv`

Create and activate a virtual environment, install dependencies, and run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000/` in a browser to view the live map UI.

By default the server listens on `0.0.0.0:5000` and uses `bus.csv` in the project root.

## Configuration

The prototype uses constants in `app.py`:
- `CSV_FILE` — path to the CSV datastore (default: `bus.csv`).
- `HOST` and `PORT` — server address and port.

For production, prefer environment-based configuration (e.g., read from `.env` or use CLI args).

## API Reference

- `POST /location`
	- Ingest OwnTracks-like JSON. Example:

```bash
curl -X POST -H "Content-Type: application/json" \
	-d '{"_type":"location","tid":"bus01","lat":17.66,"lon":75.90,"tst":1763652003}' \
	http://localhost:5000/location
```

	- Response: `201 {"status":"ok"}` on success.

- `GET /api/vehicles`
	- Returns latest location for each known device (JSON array).
	- Optional query param: `limit` to cap returned items.

- `GET /api/vehicles/<device_id>`
	- Returns last known row for `device_id` or `404` if not found.

- `GET /api/routes`
	- Serves the static `routes.json` file.

- `GET /api/stops`
	- Reads `stops.csv` and returns JSON with numeric `lat`/`lon` and boolean `approximate`.

- `GET /api/stream`
	- SSE endpoint streaming changed/latest vehicles. The UI connects to this endpoint to drive live updates.

- `GET /api/locations/all` / `GET /api/locations/latest`
	- Return raw CSV rows (may be large). Use with caution and consider protection for production.

## Frontend

- Main UI: `static/index.html` — full app JS inline (maps, SSE, controls).
- Helper file: `static/app.js` — smaller utility script; may be legacy/optional depending on your UI flow.
- UI features: live vehicle list, map markers with rotation and trails, stops and route rendering, filter controls, ETA estimates and arrivals list.

## Operational Notes & Recommendations

- Storage: Using CSV is convenient for demos but not robust under concurrent writers; consider migrating to SQLite or PostgreSQL for production workloads.
- Scaling: Endpoints often read the entire CSV into memory; this will not scale for very large logs. Implement pagination or a DB-backed store when needed.
- SSE: The current SSE loop uses blocking `time.sleep(1)` in a Flask request handler — this can block worker threads in WSGI servers. Use an async/event-backed solution (Redis pub/sub, a message broker, or an ASGI server) for production-grade streaming.

## Security & Privacy

- The app currently has no authentication and will expose location data to anyone who can reach it. Do NOT expose the server publicly without adding authentication or a secure gateway (VPN, reverse proxy with auth).
- Debug prints in `app.py` log full request headers and payloads — remove or reduce logging before production to avoid leaking info.

## Suggested Improvements / Roadmap

- Add authentication (API token, OAuth, or JWT) for ingestion and admin endpoints.
- Make `CSV_FILE` and other settings configurable via environment variables.
- Implement a database-backed storage (SQLite for local, Postgres for deployed systems) with retention/rotation.
- Improve SSE implementation with an event queue or move to an async framework.
- Add basic tests and CI checks.
- Provide a `Dockerfile` and `docker-compose.yml` for reproducible deployments.

## Troubleshooting

- If the UI shows no vehicles: confirm `bus.csv` exists and has rows, and the server is running.
- If static files aren't served: ensure the working directory contains `static/` and the app has file read permissions.

## Development

- Serve locally with `python app.py` for quick testing.
- Use the browser console and the helper `window._whereis` exposed in the UI for debugging (`fetchVehicles`, `markers`, `map`).

## Example: Send a test location

```bash
curl -X POST -H "Content-Type: application/json" \
	-d '{"tid":"testbus","lat":17.6599,"lon":75.9064,"tst":1763652003}' \
	http://localhost:5000/location
```

## Author

Arshad Perampalli

---

If you'd like, I can:
- Add `CORS(app)` and make configuration via environment variables in `app.py`.
- Add a `Dockerfile` + `docker-compose.yml` for running the service and the UI.
- Implement a small SQLite migration to replace CSV with a lightweight DB.

Tell me which change you'd like next and I'll implement it.
