# STATUS

**Live on the mini** — `https://mini.tail5ef0b2.ts.net/hiking/`, port 5056.
Architecture/spec lives in `CLAUDE.md`, ideation trail in
`docs/design-journal/`.

## Landed (2026-08-19)

- Flask backend (`backend/`): peaks/hikes/weather API, SQLite schema +
  migration ladder, dual-mounted `/hiking` routes, SPA serving.
- Svelte 5 + Vite frontend (`frontend/`): list view (NH/ADK toggle, seeded
  order, completion + group badges), detail view (meta info, Leaflet
  orientation map, `maps://` link, hike log add/edit with Open-Meteo weather
  auto-fill).
- Seed data: **all 94 peaks** (48 NH, 46 ADK), compiled via 17 parallel
  research passes. 27 "done together" groups formed from research-confirmed
  pairings (3 corrected real errors along the way — see
  `backend/data/SOURCES.md`). Progression order extends past the original
  researched-from-guides first 6 per range using a heuristic (trailless
  status, length, gain). **6 peaks have no trailhead coordinate and 2 have no
  summit coordinate** after exhaustive searching — genuinely unverifiable,
  not guessed; full list and every other caveat (elevation discrepancies
  resolved, live trail-closure flags, trailless-peak limitations) in
  `backend/data/SOURCES.md`.
- `_ops` agent (`ops/agent.py`, `ops/sweep.py`) vendored from
  `turphOps/templates/app-ops-agent`, runless-health pattern (matches
  witness). `manifest.yaml` declares hiking's own store as an honestly
  unconsumed output.
- **Deployed to the mini**: `com.hiking.app` running (launchd, port 5056),
  `tailscale serve --set-path /hiking` mounted alongside every other app
  without disturbing them, `com.turph.hiking-ops` running (30-min health
  tick). Verified live: served bundle hash matches the build, dual-mount
  resolves correctly (`matched_path` echoes the bare path), all 94 peaks
  reachable through the real tailnet URL.
- Fixed a real deploy-time bug: `infra/launchd/run-hiking.sh` and
  `.claude/skills/deploy-mini/deploy.sh` were committed without the
  executable bit, so launchd's direct exec failed with `EX_CONFIG` — masked
  locally because manual testing used `bash script.sh`, which doesn't care
  about the file's own permission. Fixed in `e4c5304`.
- Wired `com.turph.hiking-ops` into `turphOps/coherence.py`'s liveness
  catalog — [turphOS/turphOps#95](https://github.com/turphOS/turphOps/pull/95),
  **open, not yet merged/pulled to the mini** (a separate repo's PR; left for
  a deliberate merge decision rather than self-merged).

## Open

- Merge & pull [turphOps#95](https://github.com/turphOS/turphOps/pull/95) on
  the mini so the coherence auditor actually watches `com.turph.hiking-ops`.
- Generate real PWA icon PNGs — currently only an SVG favicon; the manifest
  uses it as the sole icon (`sizes: "any"`), which works but isn't the usual
  192/512 raster set the rest of the suite ships.
- Backfill the 6 trailhead / 2 summit coordinates that no source could verify
  (see `backend/data/SOURCES.md`) if/when a better source turns up.
- hiking isn't yet in `turphOps/deploy/sweep-all.sh`'s `REPOS=` list or
  `coherence.py`'s `_sweep_rows()` — the weekly automated code-health sweep
  won't pick it up until that's added (separate from the health-row wiring
  above; not done here, scope was the deploy itself).

## Fast-follows (not blocking v1)

- Detail-page live weather (cached per peak/day).
- Trail elevation-profile chart (OSM Overpass + elevation sampling) — see
  `CLAUDE.md` § Fast-follows and `docs/design-journal/001-hiking-pwa-ideation.md`.
