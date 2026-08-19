# STATUS

Nothing deployed yet — no mini runtime state to recon. This doc carries the open
queue; architecture/spec lives in `CLAUDE.md`, ideation trail in
`docs/design-journal/`.

## Open

- Build v1: list view (NH/ADK toggle, seeded progression order, group badges) +
  detail view (meta info, orientation map + `maps://` link, hike log CRUD with
  Open-Meteo weather fill).
- Compile the peak reference seed data (48 NH 4000-footers + 46 ADK 46ers:
  elevation, coords, trailhead, paper map reference, researched progression
  order) — needed before either view has anything to show.

## Fast-follows (not blocking v1)

- Detail-page live weather (cached per peak/day).
- Trail elevation-profile chart (OSM Overpass + elevation sampling) — see
  `CLAUDE.md` § Fast-follows and `docs/design-journal/001-hiking-pwa-ideation.md`.
