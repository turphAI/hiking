# 001 — Two peak lists, a preferred order, and a log — not a live hike tool

**Date:** 2026-08-19
**Status:** SCOPED · not yet building

## Where this stands

Scoped end-to-end in chat after an earlier planning thread got deleted before
anything was written down — this entry (plus `CLAUDE.md`) exists so that doesn't
happen twice. Decided: IA, data model, stack, weather approach, and what's a
fast-follow. Nothing built yet — that's deliberately the next, separate step.

## The observation

Two peak-bagging lists — NH's 48 4000-footers, the ADK 46 High Peaks — want the
same three things: a sense of order to work through them, a record of what's
actually been climbed and when, and enough per-peak reference info to prep for an
outing. Existing tools (AllTrails, peakbagger sites, spreadsheets) either try to be
in-hike companions or are too generic to carry list-specific structure like
progression order and "these go together" groupings.

## The forks

- **Progression order — manual, computed, or researched-and-seeded?** Rejected
  fully manual (no reason to reinvent an ordering by hand when good beginner
  guides already exist) and fully computed/adaptive (over-engineered for a static,
  finite list). Landed on: research a sensible beginner progression once, seed it
  as `order_index`, let it be hand-edited later if a placement is wrong.
- **"Some peaks should be done together" — a tag, or does it drive the order?**
  Grouping could plausibly gate progression (don't surface a peak as "next" until
  its whole group is queued). Decided against — groups don't always complete
  together in practice, so making progression logic depend on full-group
  completion would fight reality. Landed on: display-only tag; each peak's
  completion is tracked independently; a group just shows how many of its members
  are done.
- **Peak reference data — live API or static seed?** Checked for a reliable API
  covering these two specific fixed lists; none exists, and the data barely
  changes. A live dependency would be solving a problem that isn't there. Landed
  on: one-time researched seed (elevation, coords, trailhead, paper map
  reference), stored locally.
- **Weather — one integration or two, and how "live"?** Two distinct needs
  surfaced: filling in what the weather actually was for a logged hike (wants a
  historical-by-date lookup) vs. a live look at current trailhead conditions from
  the detail page (wants current/forecast, and is explicitly lower priority — and
  flagged as potentially noisy if several detail pages get opened in one
  session). Landed on Open-Meteo for both (free, no key, has both endpoints),
  log-form fill as v1, detail-page live weather as a later, cached fast-follow.
- **Steepness / "how spiky is this trail" — a derived stat, or the real profile?**
  Proposed a cheap version first: gain-ft-per-mile as a single comparative number.
  Rejected — a steady climb and a ridge full of punishing ups-and-downs can share
  the same number, and that's the kind of wrong that matters for trip prep, not
  just cosmetic. The real elevation profile is gettable (OSM trail geometry via
  Overpass + a free elevation-sampling API — the same open, non-scraping source
  AllTrails itself is built on) but is real, bounded effort — matching ~94 trails
  to the right OSM route is manual labor, not a flip of a switch. Pushed to a
  fast-follow rather than blocking v1/v2 on it.
- **In-hike scope creep.** Explicitly ruled out early: no live GPS, no real-time
  tracking, no offline trail caching. This is a planning-and-logging tool used at
  home, not a field companion — worth naming because most hiking-app prior art
  assumes the opposite.

## Decisions (the what + why; the how lives in `CLAUDE.md`)

- Stack, data model, view layout, port assignment (5056, checked against every
  sibling app's actual `DEPLOY.md` rather than assumed), and the weather/steepness
  decisions above are all recorded in `CLAUDE.md` rather than duplicated here —
  that's where the spec lives once an idea graduates.
- The stack itself wasn't really a choice: Flask + SQLite + Svelte 5/Vite +
  launchd + `tailscale serve` is what every sibling service app already does.
  Deviating would have been the thing that needed justifying, not the reverse.

## Still open / owed

- Whether the researched progression order actually holds up once real hikes
  start landing against it — revisit after a handful of entries.
- The OSM-route-matching effort for the elevation-profile fast-follow hasn't been
  scoped peak-by-peak yet; that's its own pass when it's picked up.

## Where the work lives

Not yet — no code exists. Architecture and data model live in `../../CLAUDE.md`.
Build order and the actual PR trail will be recorded here once building starts.
