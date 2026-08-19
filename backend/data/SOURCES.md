# Seed data sources & caveats

Full 94-peak seed (48 NH 4000-footers + 46 ADK High Peaks), compiled 2026-08-19
via 17 parallel research passes plus a first 12-peak proof batch. This
document covers methodology and known gaps for the whole set — read it
before trusting any field for real trip planning, especially trailhead
coordinates, which feed the `maps://` deep link directly.

## Methodology

Every peak's `elevation_ft`/`summit_lat`/`summit_lon` traces to a Wikipedia
infobox (GNIS/USGS-derived) unless noted otherwise. `trailhead_lat/lon` came
from official sources where they exist (fs.usda.gov for NH, dec.ny.gov for
ADK) — where no official page publishes a coordinate, a cross-checked
secondary source (lakeplacid.com, cnyhiking.com, pureadirondacks.com, or a
geocoded official street address) was used, always flagged in that peak's
research. `trail_length_mi`/`elevation_gain_ft` were **only** filled from an
official or clearly-corroborated source — 34 peaks have no verified length
and 50 have no verified gain, left `null` rather than estimated. Many of
these are trailless/herd-path peaks with no standardized route to measure in
the first place (see "Trailless peaks" below).

## Trailhead reconciliation

Several peaks share one physical trailhead, but independent research passes
sometimes found slightly different coordinates for it. Where that happened,
one canonical value was picked (by cross-batch agreement where possible) and
applied to every peak sharing that trailhead, rather than leaving small
inconsistencies between, say, Marcy's and Iroquois's pin for the same
Adirondak Loj parking lot:

- **Adirondak Loj / Heart Lake**: 44.1817, -73.9649 (the original geocoded
  value from the first 12-peak batch, kept as the standard).
- **Upper Works (Tahawus)**: 44.0862, -74.0555.
- **The Garden (Keene Valley)**: 44.1889, -73.8163.
- **AMR (Ausable Club) / St. Huberts**: 44.1508, -73.7809.
- **Corey's Road (Seward Range access)**: 44.1917, -74.2635.

None of these five are DEC-published pins — DEC's High Peaks Wilderness
interior zone pages are explicitly marked "under development" and don't
publish trailhead coordinates for most interior access points. Treat them as
"best available," not authoritative.

## Genuinely unverifiable — left null, not guessed

Six peaks have **no trailhead coordinate** after exhaustive searching (do not
route `maps://` for these without a human double-check first):
- **Mount Isolation, Cannon Mountain, Mount Liberty, Mount Flume, North
  Kinsman Mountain, South Kinsman Mountain** — no fs.usda.gov page exists for
  these trailheads (two sit on state-park land, not WMNF; the rest simply
  aren't in WMNF's recreation-site index), and no AMC page publishes GPS
  either.

Two peaks have **no summit coordinate**:
- **Wildcat D Peak** — its Wikipedia infobox has no coordinate parameter
  (only Wildcat A/"Wildcat Mountain" does).
- **West Bond** — no dedicated Wikipedia article exists (redirects to Mount
  Bond); its elevation came from a list table, but no summit pin exists there
  either.

## Elevation discrepancies, resolved for consistency

A few peaks show a different elevation in their own Wikipedia infobox vs.
Wikipedia's "Four-thousand footers" summary table (the AMC-recognized
figure). Standardized to the **summary-table value** everywhere, since that's
the definitive "is this one of the 48" reference this whole app is built
around:
- **Mount Eisenhower**: 4,780 ft used (infobox says 4,757 ft).
- **Mount Willey**: 4,285 ft used (infobox says 4,255 ft).
- **Carter Dome / Middle Carter / South Carter**: minor (~6–10 ft) infobox-vs-
  table differences exist; table values used throughout.

## Trailless / herd-path peaks

~20 ADK peaks and a few NH peaks (Owl's Head notably) have no maintained,
marked trail to the summit — reaching them requires an unmarked herd path for
some or all of the ascent. This isn't a data gap so much as a fact about the
peak: there often isn't one standardized "the route," so `trail_length_mi`/
`elevation_gain_ft` are frequently null for these (e.g. South Dix, Grace
Peak, Hough Peak — genuinely never climbed in isolation, only as part of a
multi-peak traverse, so no isolated figure exists to report).

## Live trail-condition flags (as of 2026-08-19 — re-verify before a real trip)

Several closures were active at compile time and are noted in the affected
peaks' data (not surfaced elsewhere in the app yet — check before planning):
- **Lincoln Woods Trail** (Kancamagus Hwy → Osseo Trail junction): closed
  June 15–Nov 2026 for bank-restoration work. Affects the standard approach
  to **Owl's Head, Bondcliff, Mount Bond, West Bond**.
- **Sawyer River Road**: closed to vehicles since a Dec 2023 washout, no end
  date announced. Affects **Mount Carrigain**'s Signal Ridge approach — the
  trailhead pin given is the Rt. 302 gate, not the (currently undrivable)
  traditional parking area 2 mi further up the road.

## "Done together" groups

27 groups were formed from what the research consistently flagged as a tight,
single-outing pairing (shared trailhead, same day) — not the looser "epic
traverse" combinations some peaks are occasionally part of (e.g. a full
Presidential Traverse spans 5+ peaks with genuinely different individual
defaults, so no group was forced there). A peak with no natural tight partner
has no group. See `CLAUDE.md` for how groups are used in the app (display-only,
doesn't affect progression).

Three corrections the research caught against the original assumptions this
grouping started from — worth knowing if re-deriving groups later:
- **Armstrong Mountain** is in the Great Range, not the Dix Range.
- **Blake Peak** pairs with Mount Colvin (via AMR), not the Dix Range, despite
  the shared "Dix" naming history.
- **Street Mountain** pairs with Nye Mountain (via Adirondak Loj), not
  Donaldson (via Corey's Road) — different trailhead entirely.

## Progression order (`order_index`)

The first 6 peaks per range (Tecumseh/Waumbek/Pierce/Garfield/Lafayette/
Lincoln for NH; Cascade/Porter/Phelps/Tabletop/Algonquin/Wright for ADK) were
individually researched from beginner-progression guides — see
`docs/design-journal/001-hiking-pwa-ideation.md`. The remaining 82 are
ordered by a heuristic (trailless/herd-path status, then trail length, then
elevation gain — missing values fall back to a weak elevation-based proxy),
extending the sequence rather than being individually guide-researched like
the first 6. This is explicitly a starting point, not a definitive ranking —
edit in-app if a placement feels wrong once real hikes start landing against
it.

## Full source trail

Every individual peak's specific source URLs and researcher notes are
preserved in this session's research transcripts, not duplicated into this
file peak-by-peak — this document covers the cross-cutting decisions made
during the merge. If a specific peak's number looks wrong, the fix is to
re-research that one peak, not to trust this file's summary as gospel.
