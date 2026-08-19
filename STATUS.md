# STATUS

Nothing deployed to the mini yet. Backend + frontend are built and verified
working **locally** (dev servers, not yet run on the mini). Architecture/spec
lives in `CLAUDE.md`, ideation trail in `docs/design-journal/`.

## Landed (2026-08-19, unreleased — local only)

- Flask backend (`backend/`): peaks/hikes/weather API, SQLite schema +
  migration ladder, dual-mounted `/hiking` routes, SPA serving.
- Svelte 5 + Vite frontend (`frontend/`): list view (NH/ADK toggle, seeded
  order, completion + group badges), detail view (meta info, Leaflet
  orientation map, `maps://` link, hike log add/edit with Open-Meteo weather
  auto-fill).
- Verified end-to-end in a real browser: toggle ranges, open a peak, log a
  hike, weather pre-fills from a real API call, completion + group counts
  update on return to the list.
- Deploy scaffold written (`DEPLOY.md`, `.claude/skills/deploy-mini/deploy.sh`,
  `infra/launchd/`) — mirrors witness/turphfolio exactly. **Not yet run on the
  mini** — no SSH access from this session; deploying is a separate step.
- Seed data: **all 94 peaks** (48 NH, 46 ADK), compiled via 17 parallel
  research passes and merged 2026-08-19. 27 "done together" groups formed
  from research-confirmed pairings (3 corrected real errors along the way —
  see `backend/data/SOURCES.md`). Progression order extends past the
  original researched-from-guides first 6 per range using a heuristic
  (trailless status, length, gain). **6 peaks have no trailhead coordinate
  and 2 have no summit coordinate** after exhaustive searching — genuinely
  unverifiable, not guessed; full list and every other caveat (elevation
  discrepancies resolved, live trail-closure flags, trailless-peak
  limitations) in `backend/data/SOURCES.md`.

## Open

- Deploy to the mini (one-time setup per `DEPLOY.md`) — needs to happen on
  the mini itself or via SSH, not from this laptop session.
- Two `_ops` steps deferred until real mini deployment (see `ops/README.md`):
  installing `ops/deploy/com.turph.hiking-ops.plist`, and wiring
  `com.turph.hiking-ops` into `turphOps/coherence.py`'s watcher catalog.
- Generate real PWA icon PNGs — currently only an SVG favicon; the manifest
  uses it as the sole icon (`sizes: "any"`), which works but isn't the usual
  192/512 raster set the rest of the suite ships.
- Backfill the 6 trailhead / 2 summit coordinates that no source could verify
  (see `backend/data/SOURCES.md`) if/when a better source turns up.

## Landed (2026-08-19, unreleased — local only, cont'd)

- `_ops` agent (`ops/agent.py`, `ops/sweep.py`) vendored from
  `turphOps/templates/app-ops-agent`, following the runless-health pattern
  (matches witness — interactive app, no batch runs). Verified: `python3 -m
  ops.agent` writes valid `health.json`/`quality.json`/`topology.json`; all 7
  `ops/tests` pass. `manifest.yaml` declares hiking's own store as an
  unconsumed output (honest — nothing reads it yet).

## Fast-follows (not blocking v1)

- Detail-page live weather (cached per peak/day).
- Trail elevation-profile chart (OSM Overpass + elevation sampling) — see
  `CLAUDE.md` § Fast-follows and `docs/design-journal/001-hiking-pwa-ideation.md`.
