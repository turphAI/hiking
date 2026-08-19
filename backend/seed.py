"""Load backend/data/seed_peaks.json into the peaks/groups tables.

Idempotent-ish for dev convenience: wipes and reloads peaks+groups (never
hikes — those are real logged data once they exist). Run manually:

    cd backend && python3 seed.py
"""
import json
from pathlib import Path

import db

SEED_PATH = Path(__file__).parent / "data" / "seed_peaks.json"


def run():
    peaks = json.loads(SEED_PATH.read_text())

    with db.connection() as conn:
        conn.execute("DELETE FROM peaks")
        conn.execute("DELETE FROM groups")

        group_ids = {}  # (range, name) -> id
        for i, p in enumerate(peaks):
            group_id = None
            group_name = p.get("group_name")
            if group_name:
                key = (p["range"], group_name)
                if key not in group_ids:
                    cur = conn.execute(
                        "INSERT INTO groups (range, name) VALUES (?, ?)",
                        (p["range"], group_name),
                    )
                    group_ids[key] = cur.lastrowid
                group_id = group_ids[key]

            conn.execute(
                """
                INSERT INTO peaks (
                    range, name, elevation_ft, trail_length_mi, elevation_gain_ft,
                    order_index, summit_lat, summit_lon, trailhead_name,
                    trailhead_lat, trailhead_lon, paper_map_ref, group_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    p["range"], p["name"], p.get("elevation_ft"),
                    p.get("trail_length_mi"), p.get("elevation_gain_ft"),
                    p.get("order_index", i), p.get("summit_lat"), p.get("summit_lon"),
                    p.get("trailhead_name"), p.get("trailhead_lat"), p.get("trailhead_lon"),
                    p.get("paper_map_ref"), group_id,
                ),
            )
        conn.commit()
    print(f"Seeded {len(peaks)} peaks.")


if __name__ == "__main__":
    db.init_db()
    run()
