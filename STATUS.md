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
- Seed data: **12 of 94 peaks** (6 NH, 6 ADK — enough to prove the pipeline
  and include one real group each range). Sourced from Wikipedia infoboxes,
  WMNF/AMC/ADK official pages; full provenance and confidence notes in
  `backend/data/SOURCES.md`. Trailhead coordinates for the Franconia/Cascade/
  Heart-Lake-trailhead peaks are cross-checked-but-not-official — flagged
  there for a spot-check before fully trusting them for real directions.

## Open

- Compile the remaining 82 peaks (42 NH + 40 ADK) into `seed_peaks.json`.
- Deploy to the mini (one-time setup per `DEPLOY.md`) — needs to happen on
  the mini itself or via SSH, not from this laptop session.
- Vendor the `_ops` agent from `turphOps/templates/app-ops-agent` for
  health/monitoring coverage (not started).
- Generate real PWA icon PNGs — currently only an SVG favicon; the manifest
  uses it as the sole icon (`sizes: "any"`), which works but isn't the usual
  192/512 raster set the rest of the suite ships.

## Fast-follows (not blocking v1)

- Detail-page live weather (cached per peak/day).
- Trail elevation-profile chart (OSM Overpass + elevation sampling) — see
  `CLAUDE.md` § Fast-follows and `docs/design-journal/001-hiking-pwa-ideation.md`.
