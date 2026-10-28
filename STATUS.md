# STATUS

**Live on the mini** — `https://mini.<tailnet>.ts.net/hiking/`, port 5056.
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

## Since then (as of 2026-10-24)

No user-facing feature work — everything below is ops, CI and correctness.
The app on the mini behaves as described above.

- **Weekly automated code-health sweep is live.** Sweeps have been landing
  findings in `ops/findings.json` since 2026-10-11, so hiking is in
  `turphOps/deploy/sweep-all.sh`'s `REPOS=` list now. The automated dependency
  fixer is wired up too — vite, devalue and brace-expansion advisories were
  each found and bumped without hand-holding.
- **Shared ops core.** `contract`/`issue`/`scanners` are no longer vendored
  here; they're imported from `turphOps/ops_core`, found by `ops/__init__.py`
  (turphOps journal 035). ~2,100 lines of duplicated code left the repo.
- **CI.** `.github/workflows/tests.yml` runs the backend tests (Python 3.12)
  and the ops tests (Python 3.9, matching the mini's system python) on every
  push and PR.
- **Data-integrity fix:** re-running the peak seed used to either fail the
  foreign-key check or reattach logged hikes to the wrong peak. Re-seeding now
  keeps hikes on their peaks.
- Ops hardening: the secret scanner reads every file git doesn't ignore as it
  is on disk; the sweep's code-health reviewer runs against a copy rather than
  the live repo; the sweep writes its plain-language line from the start.

## Open

- Generate real PWA icon PNGs — currently only an SVG favicon; the manifest
  uses it as the sole icon (`sizes: "any"`), which works but isn't the usual
  192/512 raster set the rest of the suite ships. **Still open** — confirmed
  2026-10-24, `frontend/public/` holds only `favicon.svg`.
- Backfill the 6 trailhead / 2 summit coordinates that no source could verify
  (see `backend/data/SOURCES.md`) if/when a better source turns up. **Still
  open** — confirmed 2026-10-24 against `seed_peaks.json`.
- Merge & pull [turphOps#95](https://github.com/turphOS/turphOps/pull/95) on
  the mini so the coherence auditor actually watches `com.turph.hiking-ops`.
  Status not verifiable from inside this repo — check it there.
- Two low-severity code-health findings are open against `backend/app.py` (a
  single-threaded server that stalls on a slow weather lookup; a file-existence
  oracle in the SPA fallback route). `ops/findings.json`, not this list, is the
  live view.

## Fast-follows (not blocking v1)

- Detail-page live weather (cached per peak/day).
- Trail elevation-profile chart (OSM Overpass + elevation sampling) — see
  `CLAUDE.md` § Fast-follows and `docs/design-journal/001-hiking-pwa-ideation.md`.
