"""Load backend/data/seed_peaks.json into the peaks/groups tables.

Safe to re-run at any time: syncs peaks+groups to the seed in place, never
touching the ids that logged hikes (real data) point at. Run manually:

    cd backend && python3 seed.py
"""
import json
from pathlib import Path

import db

SEED_PATH = Path(__file__).parent / "data" / "seed_peaks.json"


def run():
    """Sync peaks+groups to the seed WITHOUT changing the ids logged hikes point at.

    The old version deleted every peak and re-inserted them with fresh ids; with
    foreign keys on that raised as soon as any hike existed, and with them off it
    would have reattached hikes to whatever peak now held the old id. Peaks are
    matched on (range, name) and updated in place (so a fetched elevation profile
    survives too); new peaks are inserted; peaks missing from the seed are removed
    only if no hike references them."""
    peaks = json.loads(SEED_PATH.read_text())

    with db.connection() as conn:
        group_ids = {(r["range"], r["name"]): r["id"]
                     for r in conn.execute("SELECT id, range, name FROM groups")}
        peak_ids = {(r["range"], r["name"]): r["id"]
                    for r in conn.execute("SELECT id, range, name FROM peaks")}
        seen = set()
        added = updated = 0
        for i, p in enumerate(peaks):
            group_id = None
            group_name = p.get("group_name")
            if group_name:
                gkey = (p["range"], group_name)
                if gkey not in group_ids:
                    cur = conn.execute(
                        "INSERT INTO groups (range, name) VALUES (?, ?)", (p["range"], group_name))
                    group_ids[gkey] = cur.lastrowid
                group_id = group_ids[gkey]

            key = (p["range"], p["name"])
            seen.add(key)
            values = (
                p.get("elevation_ft"), p.get("trail_length_mi"), p.get("elevation_gain_ft"),
                p.get("order_index", i), p.get("summit_lat"), p.get("summit_lon"),
                p.get("trailhead_name"), p.get("trailhead_lat"), p.get("trailhead_lon"),
                p.get("paper_map_ref"), group_id,
            )
            if key in peak_ids:
                conn.execute(
                    """
                    UPDATE peaks SET
                        elevation_ft = ?, trail_length_mi = ?, elevation_gain_ft = ?,
                        order_index = ?, summit_lat = ?, summit_lon = ?, trailhead_name = ?,
                        trailhead_lat = ?, trailhead_lon = ?, paper_map_ref = ?, group_id = ?
                    WHERE id = ?
                    """,
                    (*values, peak_ids[key]),
                )
                updated += 1
            else:
                conn.execute(
                    """
                    INSERT INTO peaks (
                        range, name, elevation_ft, trail_length_mi, elevation_gain_ft,
                        order_index, summit_lat, summit_lon, trailhead_name,
                        trailhead_lat, trailhead_lon, paper_map_ref, group_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (p["range"], p["name"], *values),
                )
                added += 1

        removed = kept = 0
        for key, pid in peak_ids.items():
            if key in seen:
                continue
            cur = conn.execute(
                "DELETE FROM peaks WHERE id = ? AND NOT EXISTS (SELECT 1 FROM hikes WHERE peak_id = ?)",
                (pid, pid),
            )
            removed += cur.rowcount
            kept += 1 - cur.rowcount
        conn.execute("DELETE FROM groups WHERE id NOT IN (SELECT group_id FROM peaks WHERE group_id IS NOT NULL)")
        conn.commit()
    print(f"Seeded {len(peaks)} peaks ({added} added, {updated} updated, {removed} removed, "
          f"{kept} kept because hikes reference them).")


if __name__ == "__main__":
    db.init_db()
    run()
