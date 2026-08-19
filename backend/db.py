import sqlite3
from contextlib import contextmanager
from config import DB_PATH, DATA_DIR


def get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # Wait out a competing writer rather than raising SQLITE_BUSY.
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def connection():
    """Yield a connection that is always closed, even if the body raises."""
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS groups (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            range  TEXT NOT NULL CHECK(range IN ('NH','ADK')),
            name   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS peaks (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            range              TEXT    NOT NULL CHECK(range IN ('NH','ADK')),
            name               TEXT    NOT NULL,
            elevation_ft       INTEGER,
            trail_length_mi    REAL,
            elevation_gain_ft  INTEGER,
            order_index        INTEGER NOT NULL,
            summit_lat         REAL,
            summit_lon         REAL,
            trailhead_name     TEXT,
            trailhead_lat      REAL,
            trailhead_lon      REAL,
            paper_map_ref      TEXT,
            group_id           INTEGER REFERENCES groups(id),
            -- Fast-follow (see CLAUDE.md § Fast-follows): a JSON array of
            -- {distance_mi, elevation_ft} points, seeded from OSM + an
            -- elevation API. NULL until that pass runs — the UI treats a NULL
            -- profile as "not available yet", not an error.
            elevation_profile  TEXT,
            created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS hikes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            peak_id     INTEGER NOT NULL REFERENCES peaks(id),
            date        DATE    NOT NULL,
            -- API-fetched at entry time (Open-Meteo), user-editable after.
            weather     TEXT,
            notes       TEXT,
            created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)
        _run_migrations(conn)
        conn.commit()
    print(f"Database ready at {DB_PATH}")


def _run_migrations(conn):
    """Forward-only migration ladder keyed on PRAGMA user_version.

    The CREATE TABLE IF NOT EXISTS statements above only cover a fresh DB or
    additive-safe reruns — a real schema CHANGE (new column, backfill) on an
    existing database needs a step here. To add one: append an
    `if version < N` block, bump `version` to N, `PRAGMA user_version = N`.
    Each step runs once, in order, on every startup.
    """
    version = conn.execute("PRAGMA user_version").fetchone()[0]

    if version < 1:
        version = 1
        conn.execute(f"PRAGMA user_version = {version}")
