"""seed.run(): re-seeding must keep the peak ids that logged hikes point at
(seed-reseed-breaks-hike-fk). Run: PYTHONPATH=backend pytest backend/tests"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402
import seed  # noqa: E402


def _peak(name, **kw):
    base = {"range": "NH", "name": name, "elevation_ft": 4000, "order_index": 0, "group_name": None}
    base.update(kw)
    return base


def _setup(tmp_path, monkeypatch, peaks):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(peaks))
    monkeypatch.setattr(seed, "SEED_PATH", path)
    db.init_db()
    return path


def _peaks(conn):
    return {r["name"]: dict(r) for r in conn.execute("SELECT * FROM peaks")}


def test_reseeding_after_a_hike_is_logged_keeps_the_hike_on_the_same_peak(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, [_peak("Mount A", order_index=0), _peak("Mount B", order_index=1)])
    seed.run()
    with db.connection() as conn:
        b_id = _peaks(conn)["Mount B"]["id"]
        conn.execute("INSERT INTO hikes (peak_id, date, notes) VALUES (?, '2026-08-01', 'great day')", (b_id,))
        conn.commit()

    seed.run()                                    # used to raise IntegrityError (FK on)

    with db.connection() as conn:
        row = conn.execute("SELECT p.name, h.notes FROM hikes h JOIN peaks p ON p.id = h.peak_id").fetchone()
        assert (row["name"], row["notes"]) == ("Mount B", "great day")
        assert _peaks(conn)["Mount B"]["id"] == b_id          # same id, not a fresh one


def test_reseed_updates_changed_attributes_in_place_and_keeps_fetched_profiles(tmp_path, monkeypatch):
    path = _setup(tmp_path, monkeypatch, [_peak("Mount A", elevation_ft=4000)])
    seed.run()
    with db.connection() as conn:
        conn.execute("UPDATE peaks SET elevation_profile = '[1,2,3]' WHERE name = 'Mount A'")
        conn.commit()
    path.write_text(json.dumps([_peak("Mount A", elevation_ft=4100)]))

    seed.run()

    with db.connection() as conn:
        a = _peaks(conn)["Mount A"]
        assert a["elevation_ft"] == 4100 and a["elevation_profile"] == "[1,2,3]"


def test_a_peak_dropped_from_the_seed_goes_unless_it_has_hikes(tmp_path, monkeypatch):
    path = _setup(tmp_path, monkeypatch, [_peak("Keep", order_index=0), _peak("Gone", order_index=1),
                                          _peak("Logged", order_index=2)])
    seed.run()
    with db.connection() as conn:
        lid = _peaks(conn)["Logged"]["id"]
        conn.execute("INSERT INTO hikes (peak_id, date) VALUES (?, '2026-08-01')", (lid,))
        conn.commit()
    path.write_text(json.dumps([_peak("Keep", order_index=0)]))

    seed.run()

    with db.connection() as conn:
        assert set(_peaks(conn)) == {"Keep", "Logged"}        # Logged has a hike: never deleted


def test_groups_are_reused_not_duplicated_and_unused_ones_removed(tmp_path, monkeypatch):
    path = _setup(tmp_path, monkeypatch, [_peak("A", group_name="Pair"), _peak("B", group_name="Pair")])
    seed.run(); seed.run()
    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM groups").fetchone()["n"] == 1
    path.write_text(json.dumps([_peak("A"), _peak("B")]))     # no group any more
    seed.run()
    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM groups").fetchone()["n"] == 0
