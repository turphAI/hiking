# hiking — project memory

## What this app is

A personal progress-tracking and hike-logging tool for two peak lists: the NH 48
(4000-footers) and the ADK 46 (High Peaks). Two jobs: (1) show a preferred order to
work through each list with completion state, and (2) log basic info per hike (date,
weather, notes) plus static reference info per peak (length, elevation, trailhead,
orientation map, paper map reference).

**Not an in-hike tool.** No live GPS, no real-time tracking, no offline trail data.
Planning and logging happen at home, before/after a hike — this is confirmed scope,
not an oversight.

## Machine layout (same as the turph family)

Laptop is dev-only (write/commit/push). The mini is the sole host — pulls from
GitHub, runs the backend under launchd, serves over tailnet. Never run the backend
or any data jobs on the laptop.

## Architecture (locked)

- **Backend:** Flask, plain JSON API, no ORM. Matches witness/turphfolio/turphDocs.
- **Frontend:** Svelte 5 + Vite SPA (not SvelteKit), built to `static/`, served by
  Flask. `vite-plugin-pwa` for an installable home-screen icon — not for offline
  data caching, since this isn't used in the field.
- **Data:** local SQLite on the mini (`data/hiking.db`, gitignored), schema owned by
  `backend/db.py`, migrations via a `user_version` ladder on startup — same pattern
  as witness/turphfolio.
- **Deploy:** `.claude/skills/deploy-mini/deploy.sh` piped over SSH, launchd runner
  (`com.hiking.app`), minimal-diff build+restart. Never docker/pm2/systemd.
- **Exposure:** `tailscale serve --bg --set-path /hiking 5056` — tailnet-only, never
  Funnel. Port **5056** confirmed free by checking every app's `DEPLOY.md` on
  2026-08-19: 5050 turph, 5051 witness, 5052 turphfolio, 5053 turphDocs, 5054
  vasospasm, 5055 turphRetirement, nothing claims 5056+.
- **Auth:** none — being on the tailnet is the auth boundary, per the rest of the
  suite.
- **Ops coverage:** vendor `turphOps/templates/app-ops-agent` at build time; write
  `_ops/health.json` at minimum, following `turphOps/CONTRACT.md`.

## Data model

Three tables:

- **`peaks`** — `range` (NH|ADK), `name`, `elevation_ft`, `trail_length_mi`,
  `elevation_gain_ft`, `order_index` (seeded progression order, see below),
  summit `lat`/`lon`, `trailhead_name`, `trailhead_lat`/`lon`, `paper_map_ref`
  (text, e.g. an AMC or ADK/Nat Geo map-series name/number), `group_id` (nullable
  FK), `elevation_profile` (nullable — fast-follow, see below).
- **`groups`** — display-only tag (e.g. "Franconia Ridge"). Grouping does **not**
  affect `order_index` or progression logic — each peak's completion is tracked
  independently, and a group can be partially done. The list view shows group
  membership and a count (e.g. "2/3 done").
- **`hikes`** — `peak_id`, `date`, `weather` (API-fetched at entry time, editable),
  `notes`. Multiple hikes allowed per peak (re-climbs).

**Progression order (`order_index`) is seeded once from research, not computed at
runtime.** Sources and shape, researched 2026-08-19:
- NH 48: easy tier first (Tecumseh, Waumbek, Pierce), then build distance gradually
  (Garfield ~10mi → Carter Dome ~12mi → Isolation ~14mi) before the long ones
  (Bondcliff, Owls Head ~18mi), scrambles (Tripyramid, Flume, Owls Head's herd path)
  last. [AMC Couch-to-4K](https://www.outdoors.org/resources/amc-outdoors/outdoor-resources/couch-to-4k-hiking-nh-4000-footers-for-beginners/),
  [ridj-it](https://www.ridj-it.com/single-post/hike-48-4000-footers-new-hampshire).
- ADK 46: Cascade + Porter first (maintained trail, shortest), then Phelps,
  Tabletop, Street/Nye, Algonquin/Iroquois, Wright before trail-less/technical
  peaks. [BivWack starter peaks](https://bivwackoutdoors.com/trips/starter-peaks-for-the-adirondack-46er),
  [adkforum](https://www.adkforum.com/forum/the-adirondack-forum/general-adirondack-discussion/11448-adk-46-high-peaks-hiking-sequence).
- Editable in-app after seeding, if the researched order doesn't match reality.

**Peak reference data (elevation/coords/trailhead/paper map ref) is a one-time
static seed**, not a live API — no reliable API exists for these two fixed lists,
and the data essentially never changes.

## Views

1. **List view** — NH/ADK toggle; peaks in `order_index` order; completion state +
   metadata; group badges; a comparative steepness chart is explicitly deferred
   (see Fast-follows — a single gain/mile stat was rejected as misleading).
2. **Detail view** — static meta (length, gain, trailhead, paper map ref);
   read/add/edit hike log entries (date, weather, notes); trailhead coordinates
   with an embedded orientation-only map (Leaflet + OSM tiles, no API key — "where
   is this, roughly," not turn-by-turn) next to a `maps://?daddr=lat,lon` button
   that hands off to Apple Maps for real trip prep.

## Weather integration

Source: **Open-Meteo** (free, no API key, has both a forecast endpoint and a
historical archive endpoint by lat/lon) — covers both use cases below without
managing a secret.

- **Hike-log form (priority, v1):** on save, fetch weather for the trailhead
  lat/lon + the entered date and pre-fill the `weather` field; user can edit/
  override.
- **Detail-page live weather (nice-to-have, later):** fetch on page open. Flagged
  as noisy if browsing many detail pages in a session — cache per (peak, day)
  locally before shipping this; not a v1 blocker.

## Fast-follows (deferred, not blockers for v1 or v2)

- **Trail elevation profile chart.** Rejected the simple gain-ft/mile stat as
  misleading (hides PUDs — a steady climb and a spiky ridge can share one
  number). Real approach, researched 2026-08-19: pull the trail's path geometry
  from **OpenStreetMap via the Overpass API** (ODbL-licensed, the same source
  AllTrails itself builds its walkable-trail database from — not a scraping-ToS
  problem), then sample elevation along that polyline with a free, no-key
  elevation API (Open-Meteo's elevation endpoint takes batched lat/lon points).
  Store the resulting distance/elevation series once per peak (`peaks.elevation_profile`),
  same seed-once pattern as the rest of the peak data — no runtime dependency.
  **Real cost:** matching all 94 trails to the correct OSM route/way chain for the
  standard ascent is the labor — most will be clean, some will need manual
  verification against known route names. Render as a d3 line chart on the detail
  view once seeded.

## Open decisions

_(none outstanding as of 2026-08-19 — resolve here as they come up)_

## Dev commands

Not yet — no code exists. This section fills in once the build starts.
