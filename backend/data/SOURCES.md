# Seed data sources & caveats (compiled 2026-08-19)

Provenance for `seed_peaks.json` — a 12-peak starter batch (6 NH, 6 ADK), not
the full 94. Elevation and summit coordinates came from Wikipedia infoboxes
(USGS/GNIS-derived) in every case. Trail length / elevation gain came from
official sources (WMNF/fs.usda.gov, AMC outdoors.org, Wikipedia route
descriptions) where available — left `null` in the JSON rather than filled
from an unverified secondary source when no official figure could be found.

**Trailhead coordinates need a human spot-check before being trusted for real
driving directions** — they feed the `maps://` deep link directly. Confidence
varies by peak:

- **High confidence** (official page with explicit coordinates): Tecumseh,
  Waumbek, Pierce, Garfield — all from fs.usda.gov WMNF trailhead pages.
- **Medium confidence** (no single official page publishes a raw lat/lon;
  cross-checked between 2 independent secondary sources that agreed within
  ~20–300m): Lafayette/Lincoln (Franconia Notch), Cascade/Porter (Rt 73), and
  all four Heart Lake-trailhead ADK peaks (Phelps, Tabletop, Algonquin,
  Wright) — the Adirondak Loj coordinate was geocoded from ADK's official
  street address (1002 Adirondack Loj Rd), not copied from a published
  lat/lon.

**Known caveat:** NY DEC has been constructing a replacement Cascade/Porter
trailhead at Mt Van Hoevenberg (incomplete as of research date) — the Route
73 trailhead used here is the current, standard, open one; re-verify if that
construction has since finished.

**Nulls, and why:**
- Tecumseh, Garfield: `elevation_gain_ft` — WMNF pages give a partial
  waypoint distance, not a total gain figure.
- Waumbek: `trail_length_mi`, `elevation_gain_ft` — secondary sources
  disagreed by a wide enough margin (6.9–7.3 mi, 2,500–2,732 ft) that none
  could be called verified.
- Mount Tabletop: `elevation_gain_ft` — it's a trailless herd-path peak; the
  only figure found was an unverified personal-blog estimate, deliberately
  not used.

`paper_map_ref` values are AMC White Mountains Trail Map series / National
Geographic Trails Illustrated Map 742, assigned by region — lower-stakes than
coordinates (worst case is a wrong map number to double-check at purchase),
verified only that the map series/numbering itself is real, not
peak-by-peak against a publisher coverage diagram.

Remaining 82 peaks (42 NH + 40 ADK) are not yet compiled — this batch exists
to prove the pipeline end-to-end. See `STATUS.md`.
