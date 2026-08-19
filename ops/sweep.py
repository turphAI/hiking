"""hiking code-health sweep — the review-automation behind quality.json.

The review pass CONTRACT.md §4.7's producer model calls for: runs a
code-health review over hiking's reviewable code, reconciles the findings
into ``ops/findings.json`` (the committed ledger — the source of truth), and
refreshes ``_ops/quality.json``. Two modes:

    python3 -m ops.sweep            # full scheduled sweep — AUTHORITATIVE: open
                                    #   findings the review no longer reports are
                                    #   marked resolved
    python3 -m ops.sweep --diff     # PR-gate — review only files changed vs
                                    #   origin/main; never resolves out-of-scope
                                    #   findings

No private/sensitive data in this repo (no PHI/PII, unlike witness/insurance)
— the peak/hike data is the user's own hiking log, not a redaction concern,
so the review scope below needs no DO-NOT-read carve-out.

Design notes (identical safety model across all producers):
  - The review is one ``claude`` CLI call returning a JSON array, isolated in
    ``run_review()``. Everything load-bearing — ledger read/merge/write — is the
    contract's tested ``reconcile_findings`` / ``read_ledger`` / ``write_ledger``,
    exercised here without the model via the injectable ``review=`` seam.
  - A flaky or absent reviewer NEVER corrupts the ledger: ``run_review`` returns
    None on any failure and the sweep aborts the write.
  - The sweep writes the WORKING TREE, not git. The ledger diff is reviewed and
    committed by a human.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from ops import agent, contract, scanners

# The reviewer's vocabulary — severities/statuses from the contract, the areas
# the suite settled on (mirrors agent._VALID_AREAS). "docs" is not part of the
# LLM reviewer's vocabulary; it is reserved for the deterministic STATUS-drift
# finding injected below.
_SEVERITIES = set(contract.QUALITY_SEVERITIES)
_AREAS = {"security", "durability", "data_integrity", "efficiency"}

# Deterministic STATUS.md-drift finding (area "docs"). Not produced by the LLM:
# computed from git so it works without a reviewer and stays false-authority-free
# — it FLAGS drift, a human reconciles STATUS, and the next full sweep (drift
# gone) auto-resolves it. Threshold = commits to the code scope since STATUS.md
# was last touched.
_STATUS_DOC = "STATUS.md"
_STATUS_DRIFT_ID = "status-doc-stale"
_STATUS_DRIFT_THRESHOLD = 5

# hiking's reviewable code: the Flask backend + ops tooling itself. Frontend
# (Svelte/JS) is out of scope — _in_scope only admits .py files, matching the
# rest of the suite's Python-only sweep convention.
_SCOPE_FILES: set[str] = set()
_SCOPE_DIRS: tuple[str, ...] = ("backend/", "ops/")


def _in_scope(path: str) -> bool:
    if not path.endswith(".py"):
        return False
    if "/tests/" in path or "__pycache__/" in path:
        return False
    return path in _SCOPE_FILES or path.startswith(_SCOPE_DIRS)


REVIEW_PROMPT = (
    "You are performing a conservative code-health review of this repository's "
    "Python CODE ONLY: a personal hiking-progress-tracker's Flask backend "
    "(backend/ — peaks/hikes/weather API, SQLite schema) and its ops tooling "
    "(ops/). "
    "Report ONLY genuine, actionable issues in these areas: security, "
    "durability, data_integrity, efficiency. Output ONLY a JSON array (no prose, "
    "no code fences), where each element is:\n"
    '  {"id": "<stable-kebab-slug-of-the-issue>", "severity": "high|medium|low", '
    '"area": "security|durability|data_integrity|efficiency", '
    '"headline": "<one self-contained sentence>", "location": "<path:line>"}\n'
    "The id MUST be stable: the same underlying issue must produce the same id on "
    "a later run. Be conservative — no style nits, no speculation. If nothing "
    "material is wrong, output []."
)


def _validate_candidates(raw: list) -> list[dict]:
    """Keep only well-formed candidate findings (the reviewer supplies the
    descriptive fields; status/first_seen are reconciliation's job). Unknown
    enums or missing id/headline are dropped, not crashed on (§3.5)."""
    out: list[dict] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        fid, headline = r.get("id"), r.get("headline")
        if not (isinstance(fid, str) and fid and isinstance(headline, str) and headline):
            continue
        if r.get("severity") not in _SEVERITIES or r.get("area") not in _AREAS:
            continue
        out.append({"id": fid, "severity": r["severity"], "area": r["area"],
                    "headline": headline, "location": r.get("location")})
    return out


def _parse_review_json(stdout: str) -> list[dict] | None:
    """Pull the findings array out of ``claude --output-format json`` output: the
    CLI wraps the model's text in an envelope with a ``result`` field, and the
    array lives there (possibly with surrounding prose). Returns validated
    candidates, or None on any parse failure."""
    try:
        env = json.loads(stdout)
    except (ValueError, TypeError):
        return None
    text = env.get("result") if isinstance(env, dict) else None
    if not isinstance(text, str):
        return None
    start = text.find("[")
    if start == -1:
        return None
    # Decode the array starting at the first '[' and stop at its real end, rather
    # than spanning to the last ']' in the text — stray brackets in surrounding
    # prose (e.g. a trailing "[let me know...]") would otherwise corrupt the parse
    # and discard a valid findings array.
    try:
        arr, _ = json.JSONDecoder().raw_decode(text, start)
    except ValueError:
        return None
    return _validate_candidates(arr) if isinstance(arr, list) else None


def run_review(repo: Path, scope_files: list[str] | None = None) -> list[dict] | None:
    """Invoke the ``claude`` CLI to review the code and return validated candidate
    findings. The single un-unit-tested seam — returns None (never raises) when
    the reviewer is unavailable or its output can't be parsed, so the caller
    leaves the ledger untouched."""
    if shutil.which("claude") is None:
        return None
    prompt = REVIEW_PROMPT
    if scope_files:
        prompt += "\n\nReview ONLY these changed files:\n" + "\n".join(scope_files)
    try:
        proc = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json"],
            cwd=str(repo), capture_output=True, text=True, timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return _parse_review_json(proc.stdout)


def _git(repo: Path, *args: str, timeout: int = 20) -> str | None:
    """Best-effort git: stripped stdout, or None on any failure / non-zero exit."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def changed_files_all(repo: Path) -> set[str]:
    """All files changed vs origin/main (committed + working tree). Best-effort:
    any git failure yields an empty set."""
    diff = _git(repo, "diff", "--name-only", "origin/main...HEAD")
    wt = _git(repo, "status", "--porcelain")
    files = set(diff.splitlines()) if diff is not None else set()
    for line in (wt.splitlines() if wt else []):
        path = line[3:]  # strip the 2-char status field + its trailing space
        if " -> " in path:  # rename/copy row: "orig -> new" — keep the new path
            path = path.split(" -> ", 1)[1]
        files.add(path.strip())
    return files


def changed_code_files(repo: Path) -> list[str]:
    """In-scope Python files changed vs origin/main (committed + working tree),
    for --diff mode."""
    return sorted(f for f in changed_files_all(repo) if _in_scope(f))


def _make_status_candidate(headline: str) -> dict:
    return {"id": _STATUS_DRIFT_ID, "severity": "low", "area": "docs",
            "headline": headline, "location": _STATUS_DOC}


def status_drift_finding(*, full_sweep: bool, status_exists: bool = True,
                         threshold: int = _STATUS_DRIFT_THRESHOLD,
                         commits_since: int = 0, last_date: str | None = None,
                         code_changed: bool = False,
                         status_changed: bool = False) -> dict | None:
    """Pure decision for the STATUS-drift finding — no git, no FS, fully unit-
    tested (the git/FS reads live in ``status_drift_candidate``).

    Full sweep: flag when ``commits_since`` (commits to the code scope since
    STATUS.md last changed) reaches ``threshold``. Diff/PR-gate: flag when the
    change touches code but not STATUS.md. No STATUS.md → never flag."""
    if not status_exists:
        return None
    if full_sweep:
        if commits_since < threshold:
            return None
        when = last_date or "its last update"
        return _make_status_candidate(
            f"STATUS.md unchanged across {commits_since} commits to code since "
            f"{when} — reconcile it or confirm it still reflects reality.")
    if not code_changed or status_changed:
        return None
    return _make_status_candidate(
        "This change touches code but not STATUS.md — update STATUS.md or "
        "confirm it still reflects reality.")


def status_drift_candidate(repo: Path, *, full_sweep: bool,
                           changed_files: set[str] | None = None) -> dict | None:
    """Git/FS wrapper around ``status_drift_finding``. Reads the repo to supply
    the decision inputs; best-effort (git failure → no finding)."""
    repo = Path(repo)
    if not (repo / _STATUS_DOC).exists():
        return status_drift_finding(full_sweep=full_sweep, status_exists=False)
    if not full_sweep:
        changed = changed_files or set()
        code_changed = any(_in_scope(f) for f in changed)
        return status_drift_finding(
            full_sweep=False, code_changed=code_changed,
            status_changed=_STATUS_DOC in changed)
    last = _git(repo, "log", "-1", "--format=%H", "--", _STATUS_DOC)
    if not last:
        return None  # STATUS.md untracked / no history — nothing to compare
    scope = [*sorted(_SCOPE_FILES), *_SCOPE_DIRS]
    count = _git(repo, "rev-list", "--count", f"{last}..HEAD", "--", *scope)
    commits_since = int(count) if count and count.isdigit() else 0
    last_date = _git(repo, "log", "-1", "--format=%cs", "--", _STATUS_DOC)
    return status_drift_finding(
        full_sweep=True, commits_since=commits_since, last_date=last_date)


def sweep(repo: Path, *, full_sweep: bool, today: str, review=run_review,
          security=scanners.run_security_scan) -> dict:
    """Run one sweep: review + security scan → reconcile into the ledger → refresh
    quality.json. Returns a summary dict. ``review``/``security`` are injectable."""
    repo = Path(repo)
    ledger_path = repo / "ops" / "findings.json"
    existing, _ = contract.read_ledger(ledger_path)
    mode = "full" if full_sweep else "diff"

    scope = None
    all_changed: set[str] | None = None
    if not full_sweep:
        all_changed = changed_files_all(repo)
        if not all_changed:
            return {"mode": "diff", "skipped": "no changes vs origin/main"}
        scope = sorted(f for f in all_changed if _in_scope(f))

    # LLM review: always on a full sweep; on --diff only when in-scope code changed
    # (a secret/dependency-only change still runs the scanners below).
    if full_sweep or scope:
        candidates = review(repo, scope)
        if candidates is None:
            return {"mode": mode,
                    "error": "review unavailable or unparseable; ledger untouched"}
    else:
        candidates = []

    # Deterministic security scanners. On a full sweep an unavailable applicable
    # scanner aborts the write (None) — never risk false-resolving its findings.
    sec = security(repo, full_sweep=full_sweep, changed=all_changed)
    if sec is None:
        return {"mode": mode,
                "error": "security scan unavailable; ledger untouched"}
    candidates = candidates + sec

    # Inject the deterministic STATUS-drift finding (if any) alongside the LLM's.
    # Replace any same-id LLM finding so the deterministic one wins.
    drift = status_drift_candidate(repo, full_sweep=full_sweep, changed_files=all_changed)
    if drift:
        candidates = [c for c in candidates if c["id"] != drift["id"]] + [drift]

    reconciled = contract.reconcile_findings(
        existing, candidates, today=today, full_sweep=full_sweep)
    contract.write_ledger(ledger_path, findings=reconciled, last_reviewed=today)
    quality = agent.build_quality(repo)  # reshape the new ledger into quality.json
    return {
        "mode": "full" if full_sweep else "diff",
        "candidates": len(candidates),
        "open": quality["summary"]["open"],
        "resolved": quality["summary"]["resolved"],
        "ledger": str(ledger_path),
    }


def main(argv: list[str]) -> int:
    full = "--diff" not in argv
    today = datetime.now().date().isoformat()
    repo = Path(os.environ.get("HIKING_DIR", str(agent.DEFAULT_PROJECT_DIR)))
    result = sweep(repo, full_sweep=full, today=today)
    print("hiking-sweep:", json.dumps(result))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
