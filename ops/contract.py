"""App-agnostic ``_ops`` artifact toolkit — CANONICAL SOURCE.

Conforms to CONTRACT.md (this repo). Owns the *mechanics* of the contract —
the JSON envelope, atomic writes, timestamp formatting, the updates cap — and
knows nothing about any particular app. App-specific logic lives in each
producer's adapter (e.g. turphNewsletter ``ops/agent.py``, turphReLo
``ops/agent.py``).

VENDORED, NOT IMPORTED
======================
This is the canonical copy. Each producer repo carries a byte-identical copy of
the code below at ``ops/contract.py`` (vendored, not a runtime dependency — see
the sharing decision recorded in this repo). When you change this file:

  1. Edit here first.
  2. Copy the code (everything below this docstring) verbatim into every
     producer's ``ops/contract.py``.
  3. Bump ``SCHEMA_VERSION`` only on a breaking change to artifact shapes, in
     lockstep with CONTRACT.md §9.

Keeping a real dependency out of the producers keeps their mini deploys a no-op
(stdlib only) and decouples their release cadences.

Since CONTRACT §12 (S2): this module imports its sibling ``issue`` module by a
relative import (``from . import issue``), specifically so the byte-identical
copy resolves correctly wherever it lands — ``ops_core.issue`` here,
``ops.issue`` once vendored. **``ops/issue.py`` must be vendored alongside
this file** (same copy-verbatim step 2 above, applied to
``ops_core/issue.py``) — a producer carrying an updated ``ops/contract.py``
without ``ops/issue.py`` fails to import. Still stdlib-only end to end: this
module still shells out to nothing (no subprocess, no network) — the issue
store below is atomic-write-only; mirroring it to the mini is the laptop
orchestrator's job (``deploy/sweep-all.sh``), not this module's, the same
division ``scanners.py``'s own docstring draws for external tools.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import issue as issue_lib

# Bumped only on a breaking change to artifact shapes (CONTRACT.md §9).
SCHEMA_VERSION = 1

# updates.json is a window, not a log (CONTRACT.md §4.2).
UPDATES_CAP = 50

# Quality findings vocabulary (CONTRACT.md §4.7), ordered most-to-least urgent.
QUALITY_SEVERITIES = ("high", "medium", "low")
QUALITY_STATUSES = ("open", "resolved", "wontfix")
# Optional lifecycle refinement of `status` (CONTRACT.md §4.7), ordered along
# the open→closed path. Additive (§9): a finding without `state` reads as
# whatever its `status` implies; `status` stays the coarse, sweep-confirmed
# view existing consumers keep reading unchanged.
QUALITY_STATES = ("open", "fix_in_flight", "resolved_pending_verify",
                  "resolved", "accepted", "parked")


# --- timestamps (CONTRACT.md §3.2) ------------------------------------------


def now_iso() -> str:
    """Current time as ISO-8601 with timezone offset, seconds precision.

    Uses the host's local timezone (``astimezone()`` with no arg). Consumers
    convert for display; the contract only requires a real offset, not UTC.
    """
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def to_iso(dt: datetime) -> str:
    """Render a datetime as a contract-shaped ISO-8601 string, preserving the
    datetime's own offset. Naive datetimes are assumed UTC (defensive —
    callers should pass tz-aware)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat(timespec="seconds")


# --- envelope (CONTRACT.md §3.1) --------------------------------------------


def envelope(app: str) -> dict:
    """The top-level envelope every app-_ops JSON artifact carries."""
    return {
        "schema_version": SCHEMA_VERSION,
        "app": app,
        "generated_at": now_iso(),
    }


# --- atomic write (CONTRACT.md §3.6) ----------------------------------------


def write_json_atomic(path: Path, payload: dict) -> None:
    """Write JSON to ``path`` atomically: temp file in the same dir, fsync,
    then ``os.replace`` (atomic on POSIX), then fsync the directory so the rename
    itself is durable. A reader never sees a half-written artifact, and a
    crash/power-loss right after the rename can't lose the otherwise-atomic update
    before the directory entry reaches disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        # A bare existence check + unlink races a concurrent deleter and can
        # itself raise (e.g. PermissionError), replacing whatever exception
        # the try block was already propagating. Swallow cleanup-time errors
        # so the original failure is never masked.
        try:
            os.unlink(tmp)
        except OSError:
            pass


# --- list-item builders (CONTRACT.md §3.3, §3.4) ----------------------------


def make_event(event_id: str, at: str, kind: str, headline: str,
               detail_url: str | None = None) -> dict:
    """Build an updates event. ``event_id`` must be stable + semantic (§3.3);
    ``headline`` must stand alone with no schema knowledge (§3.4). The adapter
    is responsible for honoring those — this just shapes the dict."""
    ev = {"id": event_id, "at": at, "kind": kind, "headline": headline}
    if detail_url is not None:
        ev["detail_url"] = detail_url
    return ev


def make_finding(finding_id: str, *, severity: str, area: str, status: str,
                 headline: str, location: str | None = None,
                 first_seen: str | None = None, resolved_at: str | None = None,
                 detail_url: str | None = None, state: str | None = None,
                 fix_ref: str | None = None, verdict_reason: str | None = None,
                 verdict_at: str | None = None,
                 sweep_id: str | None = None, plain: str | None = None) -> dict:
    """Build a quality finding (CONTRACT.md §4.7). ``finding_id`` must be stable
    + semantic (§3.3) and ``headline`` must stand alone (§3.4). Optional fields
    are present-as-null so the shape is uniform. The adapter validates the enum
    values (severity/area/status) against the contract before calling this.

    The lifecycle fields are additive (§9) and OMITTED when unset, so findings
    that don't use them keep the original nine-key shape byte-for-byte:
    ``state`` (from QUALITY_STATES) refines ``status`` — see
    ``status_for_state`` for the pairing; ``fix_ref`` is free text pointing at
    the fix ("PR #50", a commit sha); ``verdict_reason`` / ``verdict_at``
    (ISO date) record why/when a human accepted or parked it; ``sweep_id``
    tags the sweep batch that first produced the finding; ``plain`` is the
    owner-facing line, what goes wrong for someone using the app (see
    ``plain_line``)."""
    f = {
        "id": finding_id,
        "severity": severity,
        "area": area,
        "status": status,
        "headline": headline,
        "location": location,
        "first_seen": first_seen,
        "resolved_at": resolved_at,
        "detail_url": detail_url,
    }
    for k, v in (("state", state), ("fix_ref", fix_ref),
                 ("verdict_reason", verdict_reason), ("verdict_at", verdict_at),
                 ("sweep_id", sweep_id), ("plain", plain)):
        if v is not None:
            f[k] = v
    return f


PLAIN_MAX = 200
# Finding fields a ledger reshaper carries into _ops/quality.json beyond the
# nine base keys: the lifecycle (who's on it, a human's verdict) and the plain
# line. Without them a let-go finding reads as open downstream.
FINDING_EXTRAS = ("state", "fix_ref", "verdict_reason", "verdict_at", "sweep_id", "plain")


def plain_line(text) -> str | None:
    """A reviewer's owner-facing line, cleaned, or None (vantage theme 8 B5).

    It says what goes wrong for someone using the app, in words the owner reads
    on his phone. A line that isn't a non-empty string, carries code (a
    backtick), or speaks in the second person (law 4: "you" is the renderer's
    job) is dropped, never repaired: no line is better than an invented one,
    and the engineer headline still stands."""
    if not isinstance(text, str):
        return None
    line = " ".join(text.split())
    if not line or "`" in line or issue_lib._SECOND_PERSON.search(line):
        return None
    return line[:PLAIN_MAX]


def status_for_state(state: str) -> str:
    """The coarse ``status`` a lifecycle ``state`` refines (CONTRACT.md §4.7).
    ``status`` stays the sweep-confirmed open/resolved/wontfix view existing
    consumers read; ``state`` carries the in-flight truth. A writer setting
    ``state`` keeps the pair coherent with this mapping. Unknown states map to
    ``"open"`` — the conservative coarse view (§3.5)."""
    return {
        "open": "open",
        "fix_in_flight": "open",
        "resolved_pending_verify": "open",
        "resolved": "resolved",
        "accepted": "wontfix",
        "parked": "wontfix",
    }.get(state, "open")


# --- artifact writers (CONTRACT.md §4.1, §4.2) ------------------------------


def write_health(ops_dir: Path, app: str, *, last_run: dict | None,
                 next_run: str | None, queue_depth: int = 0,
                 warnings: list[str] | None = None) -> dict:
    """Write ``<ops_dir>/health.json`` (CONTRACT.md §4.1)."""
    payload = {
        **envelope(app),
        "last_run": last_run,
        "next_run": next_run,
        "queue_depth": queue_depth,
        "warnings": warnings or [],
    }
    write_json_atomic(Path(ops_dir) / "health.json", payload)
    return payload


def write_updates(ops_dir: Path, app: str, events: list[dict]) -> dict:
    """Write ``<ops_dir>/updates.json`` (CONTRACT.md §4.2). Events are sorted
    newest-first by ``at``, de-duplicated by ``id`` keeping the newest, then
    capped at ``UPDATES_CAP``. Event ids are unique within updates.json
    (CONTRACT.md §3.3), so the same id emitted more than once — e.g. a digest
    rebuilt across reruns — collapses to a single event. Adapters can hand over
    events in any order without worrying about ordering, dupes, or the window."""
    ordered = sorted(events, key=lambda e: e.get("at", ""), reverse=True)
    seen: set = set()
    deduped: list[dict] = []
    for e in ordered:
        eid = e.get("id")
        if eid is not None:
            if eid in seen:
                continue
            seen.add(eid)
        deduped.append(e)
    payload = {**envelope(app), "events": deduped[:UPDATES_CAP]}
    write_json_atomic(Path(ops_dir) / "updates.json", payload)
    return payload


def write_quality(ops_dir: Path, app: str, *, findings: list[dict],
                  last_reviewed: str | None = None) -> dict:
    """Write ``<ops_dir>/quality.json`` (CONTRACT.md §4.7).

    Owns the mechanics every quality producer shares: orders findings (open
    first, then by severity high→low, then resolved/wontfix) and computes the
    summary rollup (open total, resolved total, open-by-severity). The adapter
    just hands over already-shaped findings (see ``make_finding``). Unknown
    severity/status values sort last rather than raising — the manager flags
    contract issues, it doesn't crash on them (§3.5)."""
    sev_rank = {s: i for i, s in enumerate(QUALITY_SEVERITIES)}
    status_rank = {s: i for i, s in enumerate(QUALITY_STATUSES)}
    ordered = sorted(
        findings,
        key=lambda f: (
            status_rank.get(f.get("status"), len(QUALITY_STATUSES)),
            sev_rank.get(f.get("severity"), len(QUALITY_SEVERITIES)),
            f.get("first_seen") or "",
            f.get("id") or "",
        ),
    )
    open_findings = [f for f in ordered if f.get("status") == "open"]
    summary = {
        "open": len(open_findings),
        "resolved": sum(1 for f in ordered if f.get("status") == "resolved"),
        "by_severity": {
            s: sum(1 for f in open_findings if f.get("severity") == s)
            for s in QUALITY_SEVERITIES
        },
    }
    payload = {
        **envelope(app),
        "last_reviewed": last_reviewed,
        "summary": summary,
        "findings": ordered,
    }
    write_json_atomic(Path(ops_dir) / "quality.json", payload)
    return payload


# --- quality ledger lifecycle (CONTRACT.md §4.7 producer model) -------------
# The ledger (each app's own ops/findings.json) is the source of truth a review
# sweep appends to; the agent shapes it into quality.json (write_quality above).
# These helpers own the *mechanics* a sweep shares: reading the ledger, merging
# a fresh review pass into it with stable-id semantics, and writing it back. The
# review pass itself (what produces candidate findings — an LLM, a linter) is the
# app's business and lives in the app's sweep runner.

_LEDGER_NOTE = (
    "Code-health findings ledger. Source of truth (in git). Review passes "
    "(founding sweep, scheduled sweep, PR-gate) append/update entries here; "
    "ops/agent.py shapes this into _ops/quality.json per turphOps CONTRACT.md "
    "§4.7. severity: high|medium|low. status: open|resolved|wontfix. area: "
    "security|durability|data_integrity|efficiency. Optional lifecycle (§4.7): "
    "state open|fix_in_flight|resolved_pending_verify|resolved|accepted|parked "
    "refines status; fix_ref, verdict_reason, verdict_at, sweep_id."
)


def read_ledger(path: Path) -> tuple[list, str | None]:
    """Read a findings ledger (the app's ``ops/findings.json``). Returns
    ``(findings, last_reviewed)``; missing or malformed degrades to ``([], None)``
    rather than raising (CONTRACT.md §3.5) — a broken ledger must not take the
    sweep down."""
    path = Path(path)
    if not path.is_file():
        return [], None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], None
    if not isinstance(data, dict):
        return [], None
    findings = data.get("findings")
    return (findings if isinstance(findings, list) else []), data.get("last_reviewed")


def write_ledger(path: Path, *, findings: list[dict], last_reviewed: str | None,
                 note: str = _LEDGER_NOTE) -> dict:
    """Write the findings ledger atomically. ``last_reviewed`` is the date of the
    sweep that produced ``findings``; ``note`` documents the file in-band."""
    payload = {"last_reviewed": last_reviewed, "_note": note, "findings": findings}
    write_json_atomic(Path(path), payload)
    return payload


def reconcile_findings(existing: list[dict], swept: list[dict], *, today: str,
                       full_sweep: bool, sweep_id: str | None = None) -> list[dict]:
    """Merge a review sweep's findings into the existing ledger, keyed on the
    stable finding id (CONTRACT.md §3.3). The reviewer supplies only the
    descriptive fields (id, severity, area, headline, location, plain); reconciliation
    owns status / first_seen / resolved_at (and, where a row carries the
    optional ``state``, keeps it coherent with status).

    Per-id rules:
      - in sweep, new id            → open finding, first_seen = today (stamped
                                      with ``sweep_id`` when given)
      - in sweep, ledger open       → refresh severity/area/headline/location/plain;
                                      stays open, first_seen kept. A ``state``
                                      of ``fix_in_flight`` is kept (a fix is
                                      expected to still be detectable); any
                                      other state drops back to ``open`` — the
                                      reviewer still sees the issue, so a
                                      claimed resolution didn't hold
                                      (``fix_ref`` is kept as provenance)
      - in sweep, ledger resolved   → reopen (regression): status=open,
                                      resolved_at=None, first_seen kept
      - in sweep, ledger wontfix or state accepted/parked
                                    → untouched (a human verdict the sweep must
                                      not override)
      - absent from sweep, open     → resolved (resolved_at=today; ``state``,
                                      when present, → resolved) ONLY when
                                      ``full_sweep`` (an authoritative whole-repo
                                      pass); an incremental/PR-gate sweep leaves
                                      out-of-scope findings untouched
      - absent from sweep, resolved/wontfix/accepted/parked → untouched
                                      (history and verdicts are retained)

    Existing order is preserved; brand-new findings are appended."""
    swept_by_id = {f["id"]: f for f in swept if isinstance(f, dict) and f.get("id")}
    out: list[dict] = []
    seen: set = set()
    for cur in existing:
        if not isinstance(cur, dict) or not cur.get("id"):
            continue  # drop junk rows rather than propagate them
        fid = cur["id"]
        seen.add(fid)
        fresh = swept_by_id.get(fid)
        status = cur.get("status")
        verdict = cur.get("state") in ("accepted", "parked")
        if fresh is not None:
            if status == "wontfix" or verdict:
                out.append(dict(cur))  # human verdict — left alone
                continue
            merged = dict(cur)
            for k in ("severity", "area", "headline", "location", "plain"):
                if fresh.get(k) is not None:
                    merged[k] = fresh[k]
            if status == "resolved":  # the sweep sees it again → regression
                merged["status"] = "open"
                merged["resolved_at"] = None
            if "state" in merged and merged["state"] != "fix_in_flight":
                merged["state"] = "open"  # still detected — resolution didn't hold
            out.append(merged)
        else:
            if full_sweep and status == "open" and not verdict:
                merged = dict(cur)
                merged["status"] = "resolved"
                merged["resolved_at"] = today
                if "state" in merged:
                    merged["state"] = "resolved"
                out.append(merged)
            else:
                out.append(dict(cur))

    for f in swept:
        if not isinstance(f, dict) or not f.get("id") or f["id"] in seen:
            continue
        out.append(make_finding(
            f["id"], severity=f.get("severity"), area=f.get("area"),
            status="open", headline=f.get("headline"), location=f.get("location"),
            first_seen=today, resolved_at=None, detail_url=f.get("detail_url"),
            sweep_id=sweep_id, plain=f.get("plain"),
        ))
    return out


# --- Issue record sync (CONTRACT.md §12; sweep-side, S2) --------------------
# S1 (DISPATCH-VERIFY-BRIEF) proved dispatcher.py/verifier.py as stamp writers
# for exactly the dep-npm/dep-pip + status-doc-stale domain. S2 generalizes
# the other half of §12.5's "sweep, verifier, and dispatcher converge on
# writing one object": the sweep itself becomes a stamp writer, for every
# finding kind reconcile_findings() already reconciles — not just the two
# whitelisted classes dispatcher/verifier own. ``ops/issues.json`` is the
# SAME store dispatcher.py/verifier.py already write (sibling to
# ``ops/findings.json``, inside the repo's own checkout, deliberately never
# git-committed — an untracked file never trips a dirty-repo guard).

ISSUES_REL_PATH = ("ops", "issues.json")
ISSUE_SCHEMA_VERSION = 1


def issue_store_path(repo) -> Path:
    """``<repo>/ops/issues.json`` — sibling to the findings ledger, never
    ``_ops/`` (that's the derived-artifact dir; this is repo-side truth like
    the ledger it enriches)."""
    return Path(repo).joinpath(*ISSUES_REL_PATH)


def load_issue_store(repo) -> dict:
    """The repo's ``ops/issues.json``, or an empty store when missing or
    malformed — degrade, don't crash (§3.5). Same shape dispatcher.py's own
    store carries, so both writers converge on one file."""
    try:
        data = json.loads(issue_store_path(repo).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("issues"), list):
        return {"schema_version": ISSUE_SCHEMA_VERSION, "generated_at": None,
                "issues": []}
    return data


def save_issue_store(repo, store: dict) -> None:
    """Atomic write only — no network (module docstring). The laptop
    orchestrator mirrors this file to the mini the same way it already does
    for dispatch.json/verify.json (``deploy/sweep-all.sh``)."""
    store = dict(store)
    store["schema_version"] = ISSUE_SCHEMA_VERSION
    store["generated_at"] = now_iso()
    write_json_atomic(issue_store_path(repo), store)


def issue_id_for(app: str, finding_id: str) -> str:
    """CONTRACT §3.3/§12.1 semantic id: ``<app>:finding:<semantic>``."""
    return f"{app}:finding:{finding_id}"


def _find_issue(store: dict, iid: str) -> dict | None:
    for iss in store.get("issues") or []:
        if isinstance(iss, dict) and iss.get("id") == iid:
            return iss
    return None


def _upsert_issue(store: dict, issue: dict) -> None:
    issues = store.setdefault("issues", [])
    for i, iss in enumerate(issues):
        if isinstance(iss, dict) and iss.get("id") == issue.get("id"):
            issues[i] = issue
            return
    issues.append(issue)


def _with_stamp(issue: dict, stamp: dict) -> dict:
    """Append one stamp to an existing issue's History, rebuilt through
    ``new_issue`` — the one construction path every issue goes through, so
    History is never hand-mutated (law 1). Mirrors dispatcher.py's own
    ``_with_stamp`` (duplicated rather than imported: dispatcher.py isn't
    vendored, and this module must stay independently copyable)."""
    history = list(issue.get("history") or []) + [stamp]
    return issue_lib.new_issue(
        issue["id"], kind=issue["kind"], severity=issue["severity"],
        subject=issue["subject"], standing=issue["standing"],
        account=issue["account"], history=history,
        area=issue.get("area"), audience=issue.get("audience"),
        salience=(issue.get("moment") or {}).get("salience", "normal"),
        playbook=issue.get("playbook"), links=issue.get("links"))


def _new_finding_issue(app: str, finding: dict, *, sweep_id: str | None) -> dict:
    """The issue a freshly-discovered (or founding-backfilled) finding starts
    life as: History opens with ``noticed`` — attributed to the sweep that
    found it. Generalizes dispatcher.py's own ``_new_finding_issue`` (dep/docs
    only) to every finding kind. ``acting_under`` is the sweep's own standing
    rule (not ``human-approval`` — nobody has been asked anything yet, so
    ``standing.whose`` would have no honest value; not dispatcher's whitelist
    rule either — this finding hasn't been routed to any automation)."""
    ref = sweep_id or finding.get("first_seen")
    noticed = issue_lib.stamp_noticed(
        by="sweep", at=finding.get("first_seen"),
        why="a review sweep found this finding",
        refs=[f"sweep:{ref}"] if ref else None)
    area = finding.get("area")
    return issue_lib.new_issue(
        issue_id_for(app, finding["id"]), kind="finding",
        severity=finding.get("severity") or "low",
        subject={"what": finding.get("headline") or finding["id"],
                 "where": finding.get("location") or finding["id"]},
        standing={"acting_under": "standing-rule:code-health-sweep",
                  "if_it_acts": "reversible"},
        account={"headline": finding.get("headline") or finding["id"],
                 "plain": "A code-health review sweep found this finding; "
                          "the repo's own findings ledger carries the "
                          "detail."},
        history=[noticed],
        area=area if area in issue_lib.AREAS else None)


def sync_finding_issues(repo, app: str, before: list[dict], after: list[dict],
                        *, sweep_id: str | None = None) -> dict | None:
    """Advance ``ops/issues.json`` from one sweep's before/after ledger
    snapshot — ``before`` is the ledger as read at sweep start, ``after`` is
    ``reconcile_findings``'s output. Detects exactly the transitions
    ``reconcile_findings`` itself produces (plus a one-time founding backfill)
    and maps them onto stamps — CONTRACT §4.7's own lifecycle prose,
    generalized past S1's dep/docs beachhead to every finding kind (§12.5,
    "the sweep... converge on writing one object"):

      - an ``open`` finding (in ``after``) with no matching issue yet — brand
        new this sweep, OR a founding backfill of a finding that predates
        Issue-tracking — opens one with ``noticed``.
      - an ``open`` finding whose matching issue is already settled
        (``confirmed``/``closed``) — a regression the sweep redetected —
        gets ``came back``.
      - a finding ``resolved`` this sweep (``open`` in ``before``,
        ``resolved`` in ``after``) whose matching issue isn't already settled
        gets ``confirmed — held``. No matching issue → skipped: the sweep
        confirms an issue it (or dispatcher/verifier) already opened, it
        never fabricates one purely to close it.
      - anything else — still open and already tracked, wontfix/accepted/
        parked either way, or resolved with no prior issue — is untouched.
        ``wontfix``/``accepted``/``parked`` findings are never turned into
        issues here: no verdict write-path records *who* decided that yet
        (§4.7), and a stamp's ``by`` is never fabricated (law 4).

    Only ``open``/``resolved`` status transitions drive this — ``state``
    (``fix_in_flight``/``resolved_pending_verify``) is dispatcher's and
    mark_fixed.py's to set, never the sweep's (CONTRACT §4.7's own split of
    authority).

    Returns the updated store, or ``None`` when nothing changed — a fresh
    ``load_issue_store`` + no-op write is skipped, so a caller knows whether
    there's anything to persist/mirror."""
    before_by_id = {f["id"]: f for f in before
                    if isinstance(f, dict) and f.get("id")}
    after_by_id = {f["id"]: f for f in after
                   if isinstance(f, dict) and f.get("id")}
    store = load_issue_store(repo)
    changed = False
    for fid, finding in after_by_id.items():
        status_after = finding.get("status")
        if status_after not in ("open", "resolved"):
            continue
        prior = before_by_id.get(fid)
        status_before = prior.get("status") if prior else None
        issue = _find_issue(store, issue_id_for(app, fid))
        history = issue.get("history") if issue else None
        settled = bool(history) and history[-1]["stamp"] in ("confirmed", "closed")

        try:
            if status_after == "open":
                if issue is None:
                    _upsert_issue(store, _new_finding_issue(app, finding, sweep_id=sweep_id))
                    changed = True
                elif settled:
                    _upsert_issue(store, _with_stamp(issue, issue_lib.stamp_came_back(
                        by="sweep", why="the sweep detected this finding again")))
                    changed = True
                # else: an open, unsettled issue already tracks this — nothing new.
            elif (status_after == "resolved" and status_before == "open"
                  and issue is not None and not settled):
                _upsert_issue(store, _with_stamp(issue, issue_lib.stamp_confirmed(
                    how="held", by="sweep",
                    why="the sweep no longer detects this finding",
                    refs=[f"sweep:{sweep_id}"] if sweep_id else None)))
                changed = True
        except ValueError as e:
            # A malformed candidate — most likely a reviewer's free-text
            # headline containing second-person language (law 4's "you" is a
            # rendering, never a datum check) — must not crash the whole
            # sweep. Degrade and flag, never corrupt the run (§3.5): skip
            # only this finding's Issue sync; ops/findings.json is
            # untouched, and a later, cleaner-worded sweep of the same id
            # tries again.
            print(f"contract.sync_finding_issues: skipping {fid!r} — {e}",
                  file=sys.stderr)

    if not changed:
        return None
    save_issue_store(repo, store)
    return store


# --- attention / decisions / calendar (CONTRACT.md §4.3, §4.4, §4.6) --------
# Per-app "needs-you" surfaces. Each carries the standard envelope (top-level
# `app`); the manager later folds these across apps into its own artifacts (§5).


def make_decision(decision_id: str, *, kind: str, headline: str,
                  detail_url: str | None = None, created_at: str | None = None,
                  instructions: list[str] | None = None) -> dict:
    """Build a pending-decision item (CONTRACT.md §4.3). ``id`` is stable across
    writes (§3.3); ``headline`` stands alone (§3.4). ``kind`` is free-form per
    app (suggested: verdict, confirm, tune). ``instructions`` (optional) is the
    copy-pasteable playbook turph renders when the work can't be fired as an
    action — the read-only complement to a capabilities action (§4.8)."""
    item = {
        "id": decision_id,
        "kind": kind,
        "headline": headline,
        "detail_url": detail_url,
        "created_at": created_at,
    }
    if instructions:
        item["instructions"] = list(instructions)
    return item


def write_pending_decisions(ops_dir: Path, app: str, *,
                            items: list[dict]) -> dict:
    """Write ``<ops_dir>/pending_decisions.json`` (CONTRACT.md §4.3) — things the
    app needs the user to weigh in on. Sorted oldest-first by ``created_at``
    (age-ordered). An item disappears once the app's own write path records the
    decision and the next agent run omits it."""
    ordered = sorted(items, key=lambda it: it.get("created_at") or "")
    payload = {**envelope(app), "items": ordered}
    write_json_atomic(Path(ops_dir) / "pending_decisions.json", payload)
    return payload


def make_attention_item(item_id: str, *, priority: int, headline: str,
                        detail_url: str | None = None,
                        created_at: str | None = None,
                        instructions: list[str] | None = None) -> dict:
    """Build a per-app attention item (CONTRACT.md §4.4). ``priority`` is
    0 (FYI) / 1 (normal) / 2 (now). An item also present in pending_decisions
    keeps the SAME ``id`` so the manager and turph dedupe cleanly (§4.4)."""
    item = {
        "id": item_id,
        "priority": priority,
        "headline": headline,
        "detail_url": detail_url,
        "created_at": created_at,
    }
    if instructions:
        item["instructions"] = list(instructions)
    return item


def write_attention(ops_dir: Path, app: str, *, items: list[dict]) -> dict:
    """Write ``<ops_dir>/attention.json`` — the per-app "needs you today" subset
    (CONTRACT.md §4.4). Sorted priority desc, then oldest-first by ``created_at``.
    This is a triaged subset of pending_decisions + health.warnings + app
    signals, not the full backlog — the agent decides what the user sees today."""
    ordered = sorted(
        items,
        key=lambda it: (-(it.get("priority") or 0), it.get("created_at") or ""),
    )
    payload = {**envelope(app), "items": ordered}
    write_json_atomic(Path(ops_dir) / "attention.json", payload)
    return payload


def make_calendar_event(event_id: str, *, at: str, kind: str,
                        headline: str) -> dict:
    """Build a calendar event (CONTRACT.md §4.6). ``kind``: scheduled_run,
    deadline, release, expiry, reminder (free-form, but pick something the
    manager can group on)."""
    return {"id": event_id, "at": at, "kind": kind, "headline": headline}


def write_calendar(ops_dir: Path, app: str, *, events: list[dict]) -> dict:
    """Write ``<ops_dir>/calendar.json`` — this app's upcoming events
    (CONTRACT.md §4.6). Sorted soonest-first by ``at``. The 14-day window is the
    adapter's call (it decides what to pass); this just shapes and orders."""
    ordered = sorted(events, key=lambda e: e.get("at", ""))
    payload = {**envelope(app), "events": ordered}
    write_json_atomic(Path(ops_dir) / "calendar.json", payload)
    return payload


# --- capabilities + intents (CONTRACT.md §4.8, §6.4) ------------------------
# Inbox dir under <app>/_ops/ where the consumer (turph) drops action requests
# and the producer reconciles them. The producer OWNS this dir; turph writes
# intents here but never touches a producer's output artifacts (§6.2).
INTENTS_DIRNAME = "requests"


def make_action(action_id: str, label: str, *, description: str | None = None,
                confirm: str | None = None, single_flight: bool = False,
                reversibility: str | None = None) -> dict:
    """Shape one declared action for capabilities.json (§4.8). ``action_id`` is
    stable + semantic (§3.3); ``label`` is the button text turph renders.
    ``confirm`` (if set) is the prompt turph shows before firing; ``single_flight``
    advises the consumer to disable the button while one is in flight.
    ``reversibility`` (if set) is the action's blast-radius class —
    ``read_only`` / ``reversible`` / ``one_way_door`` (§4.8) — advisory, read by the
    consumer to reason about delegation. Omitted ⇒ the consumer treats it as the
    most conservative (``one_way_door``) for any auto-run decision; it never changes
    today's tap-to-fire behavior."""
    a = {"id": action_id, "label": label, "single_flight": single_flight}
    if description is not None:
        a["description"] = description
    if confirm is not None:
        a["confirm"] = confirm
    if reversibility is not None:
        a["reversibility"] = reversibility
    return a


def write_capabilities(ops_dir: Path, app: str, *, actions: list[dict]) -> dict:
    """Write ``<ops_dir>/capabilities.json`` (§4.8) — the actions this producer
    can execute on request. turph renders a button only for declared actions;
    an app with no runnable pipeline simply never writes this file, and turph
    shows it as awareness-only. The producer owns the action vocabulary — the
    consumer never assumes what an app can do."""
    payload = {**envelope(app), "actions": actions}
    write_json_atomic(Path(ops_dir) / "capabilities.json", payload)
    return payload


def iter_intents(ops_dir: Path, actions=None):
    """Yield (path, intent_dict) for each pending intent in the inbox,
    oldest-first by ``requested_at``. Malformed files are skipped (§3.5).
    If ``actions`` is given, only intents whose ``action`` is in it are yielded.
    Producer-side: the reconcile loop iterates these, acts, then calls
    ``complete_intent``."""
    inbox = Path(ops_dir) / INTENTS_DIRNAME
    if not inbox.is_dir():
        return
    items = []
    for p in sorted(inbox.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or not data.get("action"):
            continue
        if actions is not None and data["action"] not in actions:
            continue
        items.append((data.get("requested_at") or "", p, data))
    items.sort(key=lambda t: t[0])
    for _at, p, data in items:
        yield p, data


def complete_intent(ops_dir: Path, path) -> None:
    """Mark an intent handled by moving its file into ``requests/processed/``
    — a short audit trail rather than an outright delete. Idempotent: a missing
    file is a no-op."""
    path = Path(path)
    done = Path(ops_dir) / INTENTS_DIRNAME / "processed"
    done.mkdir(parents=True, exist_ok=True)
    dest = done / path.name
    counter = 1
    while dest.exists():
        dest = done / f"{path.stem}_{counter}{path.suffix}"
        counter += 1
    try:
        path.replace(dest)
    except OSError:
        # The move (audit trail) failed, but the intent MUST still be consumed —
        # otherwise the next poll re-fires it as a duplicate off-schedule run.
        # Fall back to deleting the source; only a missing file is a clean no-op.
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as e:
            print(f"ops-intents: could not complete intent {path.name}: {e}",
                  file=sys.stderr)


# --- topology (CONTRACT.md §4.9) --------------------------------------------
# The self-expansion mechanism for the turphViz cosmos: each app declares its own
# node + outbound edges; the publisher (turphOS/turphOps publisher.py) unions them
# into the public feed. Kept separate from capabilities.json (§4.8) so an
# awareness-only app with no runnable actions still appears in the viz.

# Suggested node kinds (CONTRACT.md §4.9). Free-form — a consumer renders an
# unknown kind with a default rather than failing (§3.5).
TOPOLOGY_KINDS = ("core", "pipeline", "service", "datastore", "edge", "agent")


def make_node(node_id: str, name: str, kind: str, *, desc: str | None = None,
              emits: list[str] | None = None,
              children: list[dict] | None = None) -> dict:
    """Shape a topology node (CONTRACT.md §4.9). ``node_id`` is stable + semantic
    (§3.3) — the app slug for the app's own node, ``<app>.<part>`` for a child.
    ``kind`` is from TOPOLOGY_KINDS. ``emits`` lists the event ``kind``s this node
    can emit (lets the viz attribute events to the node). ``children`` are nested
    sub-nodes (same shape — e.g. an app's internal agents)."""
    node = {"id": node_id, "name": name, "kind": kind}
    if desc is not None:
        node["desc"] = desc
    if emits:
        node["emits"] = list(emits)
    if children:
        node["children"] = list(children)
    return node


def make_edge(to: str, *, kind: str, label: str | None = None) -> dict:
    """Shape a topology edge from this app's node to another node ``to`` (an app
    slug, or ``"turph"`` for the consumption core). ``kind`` describes the handoff
    (e.g. ``publishes``); ``label`` is optional display text."""
    edge = {"to": to, "kind": kind}
    if label is not None:
        edge["label"] = label
    return edge


def write_topology(ops_dir: Path, app: str, *, node: dict,
                   edges: list[dict] | None = None) -> dict:
    """Write ``<ops_dir>/topology.json`` (CONTRACT.md §4.9) — this app's
    self-declaration of its node + outbound edges, which the turphViz publisher
    unions into the public cosmos. Additive/optional: an app that never writes
    this file simply doesn't appear in the viz (§3.5)."""
    payload = {**envelope(app), "node": node, "edges": edges or []}
    write_json_atomic(Path(ops_dir) / "topology.json", payload)
    return payload


# --- manager-_ops artifacts (CONTRACT.md §5) --------------------------------
# Written by the manager agent (turphOS/turphOps), which synthesizes ACROSS every
# app's _ops dir. Unlike app artifacts these carry NO top-level `app` (they span
# the suite); list items that need attribution carry their own `app` field.
# Vendored into producers for byte-identical parity even though only the manager
# calls them — stdlib-only, so it costs nothing.


def manager_envelope() -> dict:
    """Top-level envelope for manager artifacts — like ``envelope()`` but with no
    ``app`` (these span the whole suite)."""
    return {"schema_version": SCHEMA_VERSION, "generated_at": now_iso()}


def write_text_atomic(path: Path, text: str) -> None:
    """Atomic text write (for today.md). Same guarantee as ``write_json_atomic``:
    a reader never sees a half-written file, and the rename is made durable with a
    directory fsync so a crash right after it can't lose the update."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        # A bare existence check + unlink races a concurrent deleter and can
        # itself raise (e.g. PermissionError), replacing whatever exception
        # the try block was already propagating. Swallow cleanup-time errors
        # so the original failure is never masked.
        try:
            os.unlink(tmp)
        except OSError:
            pass


def write_today(ops_dir: Path, *, apps_seen: list[str], body: str) -> str:
    """Write ``<ops_dir>/today.md`` — the manager's note (CONTRACT.md §5.1).
    Emits required YAML frontmatter (schema_version, generated_at, apps_seen)
    then the markdown ``body`` (turph renders it as .prose). ``apps_seen`` is the
    apps the manager successfully read this run. Returns the full document."""
    seen = "[" + ", ".join(apps_seen) + "]"
    front = (
        "---\n"
        f"schema_version: {SCHEMA_VERSION}\n"
        f"generated_at: {now_iso()}\n"
        f"apps_seen: {seen}\n"
        "---\n\n"
    )
    text = front + body.strip() + "\n"
    write_text_atomic(Path(ops_dir) / "today.md", text)
    return text


def make_manager_attention_item(item_id: str, *, app: str, priority: int,
                                headline: str, detail_url: str | None = None,
                                instructions: list[str] | None = None) -> dict:
    """Build a manager attention item (CONTRACT.md §5.2). ``item_id`` is the
    app-prefixed id (``"<app>:<slug>"``, §3.3) so cross-app dedup is unambiguous;
    ``app`` is the owning app."""
    item = {
        "id": item_id,
        "app": app,
        "priority": priority,
        "headline": headline,
        "detail_url": detail_url,
    }
    if instructions:
        item["instructions"] = list(instructions)
    return item


def write_manager_attention(ops_dir: Path, *, items: list[dict]) -> dict:
    """Write ``<ops_dir>/attention.json`` — deduped, cross-app, prioritized
    (CONTRACT.md §5.2). No top-level ``app``; each item carries its own. Sorted
    priority desc. The manager owns this user-facing list — it may demote or drop
    app-supplied items (discipline against alert fatigue)."""
    ordered = sorted(items, key=lambda it: -(it.get("priority") or 0))
    payload = {**manager_envelope(), "items": ordered}
    write_json_atomic(Path(ops_dir) / "attention.json", payload)
    return payload


def write_manager_calendar(ops_dir: Path, *, events: list[dict]) -> dict:
    """Write ``<ops_dir>/calendar.json`` — merged, sorted, app-attributed
    (CONTRACT.md §5.3). Same event shape as §4.6 but each event carries an
    ``app`` field and there is no top-level ``app``. Sorted soonest-first."""
    ordered = sorted(events, key=lambda e: e.get("at", ""))
    payload = {**manager_envelope(), "events": ordered}
    write_json_atomic(Path(ops_dir) / "calendar.json", payload)
    return payload


# Suite roll-up colors (CONTRACT.md §5.4), worst-to-best.
STATUS_OVERALL = ("red", "amber", "green")
# App statuses the manager rolls up: the health status (§4.1) plus "unknown"
# when an app has no readable health.json.
APP_STATUSES = ("ok", "stale", "failed", "unknown")


def make_status_app(app: str, *, status: str, last_run: str | None = None,
                    contract_issues: list[str] | None = None) -> dict:
    """Build one app entry for status.json (CONTRACT.md §5.4). ``status`` is the
    app's health status (or ``"unknown"`` if unreadable). ``contract_issues`` lists
    schema problems the manager found in this app's artifacts (§3.5)."""
    return {
        "app": app,
        "status": status,
        "last_run": last_run,
        "contract_issues": contract_issues or [],
    }


def derive_overall(apps: list[dict]) -> str:
    """Roll app statuses up to a single suite color (CONTRACT.md §5.4): any
    ``failed`` → red; any non-ok (stale/unknown) or any contract issue → amber;
    otherwise green."""
    statuses = {a.get("status") for a in apps}
    if "failed" in statuses:
        return "red"
    if (statuses - {"ok"}) or any(a.get("contract_issues") for a in apps):
        return "amber"
    return "green"


def write_status(ops_dir: Path, *, apps: list[dict],
                 overall: str | None = None) -> dict:
    """Write ``<ops_dir>/status.json`` — at-a-glance suite roll-up (CONTRACT.md
    §5.4). ``overall`` is derived from the app statuses when not given. ``apps`` is
    a list of ``make_status_app`` entries (problems-first ordering is the
    adapter's call)."""
    payload = {
        **manager_envelope(),
        "overall": overall or derive_overall(apps),
        "apps": apps,
    }
    write_json_atomic(Path(ops_dir) / "status.json", payload)
    return payload
