# hiking `_ops`

hiking is interactive (Flask web app, like witness) — no batch runs, so
there's no "did the job run" signal to report. The `_ops` agent runs on a
30-minute cron regardless, reporting a runless-but-healthy status so the
suite's manager reads hiking as `ok` rather than `unknown` forever.

## What it reads → writes

| Reads (hiking's own) | Writes (`_ops/`) |
|---|---|
| (nothing — runless health) | `health.json` (CONTRACT §4.1) |
| `ops/findings.json` — committed code-health ledger | `quality.json` (CONTRACT §4.7) |
| (static) | `topology.json` (CONTRACT §4.9) |

It **does not know any other app exists** (CONTRACT §1). Pure read over
hiking's own artifacts, pure write into hiking's `_ops/`.

- **`ops/agent.py`** (`com.turph.hiking-ops`, every 30 min) — health,
  topology, and reshapes the findings ledger into `quality.json`.

hiking does **not** produce `attention.json`, `pending_decisions.json`,
`costs.json`, or `calendar.json` — there's no real data behind any of them
yet (no spend, no decisions needing a verdict, nothing scheduled). Adding one
of these later means there's real data to report, not a template to fill in
for completeness.

## Code health (CONTRACT §4.7)

Follows the suite's ledger model: a committed findings ledger
(`ops/findings.json`) is the source of truth; the agent reshapes it into
`quality.json`; reviewing is decoupled into **`ops/sweep.py`** — a weekly
full `claude`-CLI pass (`com.turph.hiking-sweep`, run centrally from the
laptop's `sweep-all.sh`) plus a `--diff` PR-gate mode.

No private/sensitive data lives in this repo (the hike log is the user's own
data, not PHI/PII requiring redaction like witness/insurance), so the sweep
scope carries no DO-NOT-read carve-out — it reviews `backend/` and `ops/`
(Python only; the Svelte frontend is out of scope, matching the rest of the
suite's sweep convention).

## Running / tests

```sh
cd ~/Projects/hiking && python3 -m ops.agent       # refresh health/quality/topology
cd ~/Projects/hiking && python3 -m ops.sweep        # full code-health sweep (needs `claude`)
~/Projects/turphOps/.venv/bin/python -m pytest ops/tests -q
```

`contract.py` and `scanners.py` are **byte-identical vendored copies** of
`turphOS/turphOps/ops_core/`. Do not edit them here — edit the canonical and
re-vendor.

## Not yet wired up

This was authored before hiking was deployed to the mini (see `STATUS.md`).
Two steps from `turphOps/docs/authoring-an-app-ops-agent.md` are deliberately
deferred until real deployment, since they only make sense for a job that's
actually running:

- **Installing the plist** (`ops/deploy/com.turph.hiking-ops.plist`) on the mini.
- **Wiring `com.turph.hiking-ops` into `turphOps/coherence.py`'s watcher
  catalog** (step 8) — a catalog row for a job that isn't running yet would
  be its own kind of drift.
