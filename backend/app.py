"""
hiking Flask API.

Thin HTTP wrappers over db.py — routes validate input, run a query, jsonify
the result. Served under /hiking on the tailnet (tailscale mounts it there;
turph owns the root). Every route is dual-mounted under both the bare path
and a /hiking-prefixed path so it resolves whether tailscale strips the
mount prefix before forwarding or preserves it — GET /api/health echoes the
matched path so the live behavior is observable with one request.
"""
import os
import re
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory

import db
import weather as weather_svc
from config import DATA_DIR

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "static"

app = Flask(__name__)

# Ensure the schema exists and any pending migrations run on every startup.
db.init_db()

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _route(method, rule, **opts):
    """Register a view under both `rule` and `/hiking + rule`.

    tailscale's path mount may strip or preserve the /hiking prefix before
    forwarding; dual-mounting makes the app correct under either behavior.
    """

    def decorator(fn):
        app.add_url_rule(rule, fn.__name__, fn, methods=[method], **opts)
        app.add_url_rule(
            "/hiking" + rule, fn.__name__ + "_w", fn, methods=[method], **opts
        )
        return fn

    return decorator


def _is_iso_date(value) -> bool:
    if not isinstance(value, str) or not _ISO_DATE_RE.match(value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _clean(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _peak_row_to_dict(row, hike_count):
    return {
        "id": row["id"],
        "range": row["range"],
        "name": row["name"],
        "elevation_ft": row["elevation_ft"],
        "trail_length_mi": row["trail_length_mi"],
        "elevation_gain_ft": row["elevation_gain_ft"],
        "order_index": row["order_index"],
        "trailhead_name": row["trailhead_name"],
        "group_id": row["group_id"],
        "group_name": row["group_name"],
        "completed": hike_count > 0,
        "hike_count": hike_count,
    }


# ── Peaks ────────────────────────────────────────────────────────────────


@_route("GET", "/api/peaks")
def list_peaks():
    range_ = request.args.get("range")
    if range_ not in ("NH", "ADK"):
        return jsonify({"error": "range_required", "expected": ["NH", "ADK"]}), 400

    with db.connection() as conn:
        rows = conn.execute(
            """
            SELECT p.*, g.name AS group_name,
                   (SELECT COUNT(*) FROM hikes h WHERE h.peak_id = p.id) AS hike_count
            FROM peaks p
            LEFT JOIN groups g ON g.id = p.group_id
            WHERE p.range = ?
            ORDER BY p.order_index ASC
            """,
            (range_,),
        ).fetchall()

    return jsonify([_peak_row_to_dict(r, r["hike_count"]) for r in rows])


@_route("GET", "/api/peaks/<int:peak_id>")
def get_peak(peak_id):
    with db.connection() as conn:
        peak = conn.execute(
            """
            SELECT p.*, g.name AS group_name
            FROM peaks p
            LEFT JOIN groups g ON g.id = p.group_id
            WHERE p.id = ?
            """,
            (peak_id,),
        ).fetchone()
        if peak is None:
            return jsonify({"error": "not_found"}), 404

        hikes = conn.execute(
            "SELECT id, date, weather, notes FROM hikes WHERE peak_id = ? ORDER BY date DESC",
            (peak_id,),
        ).fetchall()

    result = dict(peak)
    result["hikes"] = [dict(h) for h in hikes]
    return jsonify(result)


# ── Hikes (add / read / edit) ───────────────────────────────────────────


@_route("POST", "/api/hikes")
def create_hike():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "invalid_body"}), 400

    peak_id = body.get("peak_id")
    hike_date = body.get("date")
    if not isinstance(peak_id, int):
        return jsonify({"error": "peak_id_required"}), 400
    if not _is_iso_date(hike_date):
        return jsonify({"error": "invalid_date"}), 400

    with db.connection() as conn:
        peak = conn.execute("SELECT id FROM peaks WHERE id = ?", (peak_id,)).fetchone()
        if peak is None:
            return jsonify({"error": "peak_not_found"}), 404

        cur = conn.execute(
            "INSERT INTO hikes (peak_id, date, weather, notes) VALUES (?, ?, ?, ?)",
            (peak_id, hike_date, _clean(body.get("weather")), _clean(body.get("notes"))),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, peak_id, date, weather, notes FROM hikes WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()

    return jsonify(dict(row)), 201


@_route("PUT", "/api/hikes/<int:hike_id>")
def update_hike(hike_id):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "invalid_body"}), 400

    with db.connection() as conn:
        existing = conn.execute("SELECT * FROM hikes WHERE id = ?", (hike_id,)).fetchone()
        if existing is None:
            return jsonify({"error": "not_found"}), 404

        hike_date = body.get("date", existing["date"])
        if not _is_iso_date(hike_date):
            return jsonify({"error": "invalid_date"}), 400

        weather = _clean(body.get("weather")) if "weather" in body else existing["weather"]
        notes = _clean(body.get("notes")) if "notes" in body else existing["notes"]

        conn.execute(
            "UPDATE hikes SET date = ?, weather = ?, notes = ? WHERE id = ?",
            (hike_date, weather, notes, hike_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, peak_id, date, weather, notes FROM hikes WHERE id = ?", (hike_id,)
        ).fetchone()

    return jsonify(dict(row))


# ── Weather ──────────────────────────────────────────────────────────────


@_route("GET", "/api/weather")
def get_weather():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_lat_lon"}), 400

    date_str = request.args.get("date")
    if not _is_iso_date(date_str):
        return jsonify({"ok": False, "error": "invalid_date"}), 400

    return jsonify(weather_svc.get_weather(lat, lon, date_str))


# ── Health (diagnostic) ─────────────────────────────────────────────────


@_route("GET", "/api/health")
def health():
    return jsonify({"ok": True, "service": "hiking", "matched_path": request.path})


# ── SPA serving ──────────────────────────────────────────────────────────


@app.get("/hiking")
def hiking_redirect():
    return redirect("/hiking/", 301)


def _serve_spa(path=""):
    if path:
        candidate = STATIC_DIR / path
        if candidate.is_file():
            return send_from_directory(str(STATIC_DIR), path)
    index_path = STATIC_DIR / "index.html"
    if index_path.is_file():
        return send_from_directory(str(STATIC_DIR), "index.html")
    return (
        "hiking backend running, but the frontend isn't built yet. "
        "Run `npm run build` in frontend/.",
        200,
        {"Content-Type": "text/plain; charset=utf-8"},
    )


# Serve the SPA at every shape so it works whether tailscale strips the
# /hiking mount prefix or preserves it. Registered last so /api rules win.
app.add_url_rule("/", "spa_root_bare", _serve_spa)
app.add_url_rule("/hiking/", "spa_root", _serve_spa)
app.add_url_rule("/hiking/<path:path>", "spa_sub", _serve_spa)
app.add_url_rule("/<path:path>", "spa_bare", _serve_spa)


def _refuse_unsafe_debug(debug: bool, host: str) -> None:
    """Refuse debug=True on a non-loopback host — Werkzeug's debugger is RCE
    on a network-reachable bind."""
    if debug and host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit(
            "refusing to start: HIKING_DEBUG enables Werkzeug's RCE debugger and "
            f"HIKING_HOST={host!r} is not loopback. Unset HIKING_DEBUG or bind to 127.0.0.1."
        )


if __name__ == "__main__":
    host = os.environ.get("HIKING_HOST", "127.0.0.1")
    port = int(os.environ.get("HIKING_PORT", "5056"))
    debug = os.environ.get("HIKING_DEBUG", "").lower() in ("1", "true", "yes")
    _refuse_unsafe_debug(debug, host)
    app.run(host=host, port=port, debug=debug)
