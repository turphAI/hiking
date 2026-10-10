"""hiking-_ops agent.

hiking-specific adapter over the vendored ``contract`` toolkit
(turphOS/turphOps CONTRACT.md §4). Like witness, hiking is an interactive
Flask service with no batch "runs" — its ``_ops`` substrate is a committed
code-quality findings ledger (``ops/findings.json``), produced by review
passes (a founding sweep, then a periodic scheduled sweep + a PR-gate). This
agent shapes that ledger into ``_ops/quality.json`` per CONTRACT.md §4.7.

Pure-read over hiking's own ledger + pure-write into hiking's ``_ops/`` dir.
Knows no other app exists (CONTRACT.md §1). Stdlib only — runs on the mini's
system python3.

Run (CONTRACT.md §7.1, periodic mode):
    cd ~/Projects/hiking && python3 -m ops.agent
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ops import contract

APP = "hiking"

# Overridable via env so tests/CI can point at a fixture tree. Matches the
# HIKING_* env-var prefix already used by backend/config.py and app.py.
DEFAULT_PROJECT_DIR = Path.home() / "Projects" / "hiking"

# Valid finding vocabularies. Severities/statuses come from the contract;
# areas are the four axes the suite settled on (CONTRACT.md §4.7).
_VALID_SEVERITIES = set(contract.QUALITY_SEVERITIES)
_VALID_STATUSES = set(contract.QUALITY_STATUSES)
_VALID_AREAS = {"security", "durability", "data_integrity", "efficiency", "docs"}


def load_ledger(ledger_path: Path) -> tuple[list, str | None]:
    """Read the findings ledger. Returns ``(raw_findings, last_reviewed)``.

    Missing or malformed ledger degrades to ``([], None)`` rather than raising
    (CONTRACT.md §3.5) — a broken ledger must not take the agent down.
    """
    if not ledger_path.is_file():
        return [], None
    try:
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [], None
    if not isinstance(data, dict):
        return [], None
    raw = data.get("findings")
    return (raw if isinstance(raw, list) else []), data.get("last_reviewed")


def shape_findings(raw: list) -> list[dict]:
    """Validate + normalize ledger rows into contract findings. Rows that
    aren't dicts, lack a stable id/headline, or carry an unknown
    severity/status/area are skipped — the ledger is sweep/hand-authored, so
    we defend against typos rather than emit a finding the manager will choke
    on (CONTRACT.md §3.5)."""
    shaped: list[dict] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        fid = r.get("id")
        headline = r.get("headline")
        if not (isinstance(fid, str) and fid):
            continue
        if not (isinstance(headline, str) and headline):
            continue
        if r.get("severity") not in _VALID_SEVERITIES:
            continue
        if r.get("status") not in _VALID_STATUSES:
            continue
        if r.get("area") not in _VALID_AREAS:
            continue
        shaped.append(contract.make_finding(
            fid,
            severity=r["severity"],
            area=r["area"],
            status=r["status"],
            headline=headline,
            location=r.get("location"),
            first_seen=r.get("first_seen"),
            resolved_at=r.get("resolved_at"),
            detail_url=r.get("detail_url"),
            **{k: r[k] for k in contract.FINDING_EXTRAS if r.get(k) is not None},
        ))
    return shaped


def build_quality(project_dir: Path) -> dict:
    """Read ``<project_dir>/ops/findings.json`` and write
    ``<project_dir>/_ops/quality.json``. Returns the written payload."""
    project_dir = Path(project_dir)
    ledger = project_dir / "ops" / "findings.json"
    ops_dir = project_dir / "_ops"
    raw, last_reviewed = load_ledger(ledger)
    return contract.write_quality(
        ops_dir, APP, findings=shape_findings(raw), last_reviewed=last_reviewed
    )


def build_health(project_dir: Path) -> dict:
    """Emit a minimal ``health.json`` (CONTRACT.md §4.1).

    hiking is interactive — it has no batch runs to report. But an app that
    emits no health at all reads as ``unknown`` in the manager's suite
    roll-up, which drags ``status.json`` to amber forever. So hiking reports
    in with a runless-but-healthy health: ``last_run`` null (honest — there
    are no runs), no schedule, no warnings. The manager classifies a
    present-but-runless health as ``ok`` rather than ``unknown``."""
    return contract.write_health(
        Path(project_dir) / "_ops", APP,
        last_run=None, next_run=None, warnings=[],
    )


def build_topology(project_dir: Path) -> dict:
    """Declare hiking's place in the suite cosmos (CONTRACT.md §4.9) — the
    turphViz publisher unions every app's node + edges into the public feed.
    hiking is awareness-only here: it surfaces code-health metadata, never
    the hike log itself."""
    return contract.write_topology(
        Path(project_dir) / "_ops", APP,
        node=contract.make_node(
            APP, "Hiking", "service",
            desc="NH 4000-footer & ADK 46 progress tracker and hike log; "
                 "only code-health metadata surfaces."),
        edges=[contract.make_edge("turph", kind="publishes", label="quality")],
    )


def main() -> None:
    project_dir = Path(os.environ.get("HIKING_DIR", str(DEFAULT_PROJECT_DIR)))
    build_health(project_dir)
    build_topology(project_dir)
    payload = build_quality(project_dir)
    s = payload["summary"]
    print(
        f"hiking-ops: health=ok (interactive, no runs) quality open={s['open']} "
        f"(high={s['by_severity']['high']} med={s['by_severity']['medium']} "
        f"low={s['by_severity']['low']}) resolved={s['resolved']} "
        f"-> {project_dir / '_ops'}"
    )


if __name__ == "__main__":
    main()
