"""
Simple GPS tracking server (OwnTracks friendly).
Authentication removed as requested.
"""

import os
import csv
import json
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory, abort, Response
import time

# ============================
# CONFIG
# ============================
CSV_FILE = "bus.csv"
HOST = "0.0.0.0"
PORT = 5000

app = Flask(__name__, static_folder="static")


# ============================
# Initialize CSV
# ============================
def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "device_id", "latitude", "longitude", "accuracy",
                "provider", "timestamp_iso", "timestamp_raw",
                "received_at", "raw_json"
            ])


# ============================
# Timestamp Parser
# ============================
def parse_timestamp(data):
    """Supports OwnTracks timestamps."""
    if not isinstance(data, dict):
        now = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
        return now, None

    # ISO timestamp
    if isinstance(data.get("timestamp"), str):
        return data["timestamp"], data["timestamp"]

    # OwnTracks UNIX timestamp
    tst = data.get("tst")
    if isinstance(tst, (int, float)):
        dt = datetime.fromtimestamp(tst, tz=timezone.utc)
        return dt.isoformat(), tst

    # fallback
    now = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    return now, None


# ============================
# /location endpoint
# ============================
@app.route("/location", methods=["POST"])
def location():
    data = request.get_json(force=True, silent=True)

    print("\n---- NEW /location REQUEST ----")
    print("Remote addr:", request.remote_addr)
    print("Headers:", dict(request.headers))
    print("DEBUG BODY RECEIVED:", data)

    if data is None:
        return jsonify({"error": "missing json"}), 400

    # Ignore OwnTracks status messages
    if data.get("_type") == "status":
        print("DEBUG: Ignored status message")
        return jsonify({"status": "ignored"}), 200

    # Parse fields (OwnTracks friendly)
    device_id = (
        data.get("device_id") or
        data.get("tid") or
        data.get("topic") or
        "unknown"
    )

    lat = data.get("lat") or data.get("latitude")
    lon = data.get("lon") or data.get("longitude")

    accuracy = data.get("accuracy") or data.get("acc") or ""
    provider = data.get("provider") or data.get("t") or data.get("source") or ""

    timestamp_iso, timestamp_raw = parse_timestamp(data)
    received_at = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    # Validate lat/lon
    try:
        lat_val = float(lat)
        lon_val = float(lon)
    except Exception:
        print("DEBUG BAD LAT/LON:", lat, lon)
        return jsonify({"error": "bad lat/lon"}), 400

    # Save to CSV
    raw_json = json.dumps(data, ensure_ascii=False)

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            device_id, lat_val, lon_val, accuracy, provider,
            timestamp_iso, timestamp_raw, received_at, raw_json
        ])

    print(f"DEBUG: Stored location for {device_id} lat={lat_val} lon={lon_val}")
    return jsonify({"status": "ok"}), 201


# ============================
# /locations/recent (NO AUTH)
# ============================
@app.route("/locations/recent")
def recent_locations():
    limit = int(request.args.get("limit", 100))

    try:
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            rows = reader[-limit:]
    except:
        rows = []

    return jsonify(rows)


# ============================
# Helper: Latest locations per device
# ============================
def get_latest_locations():
    """Return a list with the latest row for each device_id."""
    try:
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            latest = {}
            for row in reader:
                device = row.get("device_id", "unknown")
                latest[device] = row
            # return as list
            out = []
            for dev, row in latest.items():
                try:
                    row["latitude"] = float(row.get("latitude", 0))
                    row["longitude"] = float(row.get("longitude", 0))
                except Exception:
                    row["latitude"] = None
                    row["longitude"] = None
                out.append(row)
            return out
    except Exception:
        return []


# ============================
# API: vehicles
# ============================
@app.route("/api/vehicles")
def api_vehicles():
    """Return latest location for all known devices."""
    limit = int(request.args.get("limit", 0))
    vehicles = get_latest_locations()
    if limit and isinstance(limit, int) and limit > 0:
        vehicles = vehicles[:limit]
    return jsonify(vehicles)


@app.route("/api/vehicles/<device_id>")
def api_vehicle(device_id):
    vehicles = get_latest_locations()
    for v in vehicles:
        if v.get("device_id") == device_id:
            return jsonify(v)
    return jsonify({}), 404


# ============================
# API: routes (static JSON file)
# ============================
@app.route('/api/routes')
def api_routes():
    routes_file = os.path.join(os.path.dirname(__file__), 'routes.json')
    if not os.path.exists(routes_file):
        return jsonify([])
    try:
        with open(routes_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return jsonify(data)
    except Exception:
        return jsonify([])


# ============================
# API: stops (CSV to JSON)
# ============================
@app.route('/api/stops')
def api_stops():
    stops_file = os.path.join(os.path.dirname(__file__), 'stops.csv')
    if not os.path.exists(stops_file):
        print('[stops] stops.csv not found at', stops_file)
        return jsonify([])
    try:
        with open(stops_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            out = []
            for row in reader:
                # normalize types
                try:
                    row['lat'] = float(row.get('lat'))
                    row['lon'] = float(row.get('lon'))
                except Exception:
                    print('[stops] invalid lat/lon row skipped:', row)
                    continue
                row['approximate'] = row.get('approximate') in ('1', 'true', 'True')
                out.append(row)
            print(f'[stops] served {len(out)} stops')
            return jsonify(out)
    except Exception as e:
        print('[stops] error reading stops.csv:', e)
        return jsonify([])


# ============================
# API: live stream (Server-Sent Events)
# ============================
@app.route('/api/stream')
def api_stream():
    def event_stream():
        last_sent = {}
        # Simple loop; in production consider async/event queue
        while True:
            vehicles = get_latest_locations()
            changed = []
            for v in vehicles:
                dev = v.get('device_id')
                coords = (v.get('latitude'), v.get('longitude'))
                if last_sent.get(dev) != coords:
                    last_sent[dev] = coords
                    changed.append(v)
            if changed:
                try:
                    payload = json.dumps(changed, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                except Exception:
                    pass
            time.sleep(1)
    return Response(event_stream(), mimetype='text/event-stream')


# ============================
# API: CSV raw fetch
# ============================
@app.route('/api/locations/all')
def api_locations_all():
    """Return all location rows from the CSV (could be large)."""
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = list(csv.DictReader(f))
            return jsonify(reader)
    except Exception:
        return jsonify([])


@app.route('/api/locations/latest')
def api_locations_latest():
    """Return the most recent (last) location row from the CSV."""
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = list(csv.DictReader(f))
            if reader:
                return jsonify(reader[-1])
            return jsonify({})
    except Exception:
        return jsonify({})


# ============================
# Serve static map UI
# ============================
@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("static", path)


# ============================
# Main
# ============================
if __name__ == "__main__":
    init_csv()
    print(f"Starting server on {HOST}:{PORT} (CSV_FILE={CSV_FILE})")
    app.run(host=HOST, port=PORT)
