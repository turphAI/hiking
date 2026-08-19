"""Deterministic security scanners for the code-health sweep — CANONICAL SOURCE.

Alongside the sweep's LLM code-health review sit two deterministic scanners for
the class of issue a prose review structurally can't catch reliably: known-
vulnerable dependencies (pip-audit for Python, npm audit for JS) and committed
secrets (gitleaks). Their findings flow into the existing ``security`` area of
each app's findings ledger — no new artifact (turphOps CONTRACT.md §4.7).

VENDORED, NOT IMPORTED
======================
Like ``contract.py``, this is the canonical copy. Each producer repo carries a
byte-identical copy at ``ops/scanners.py`` (vendored, not a runtime dependency),
imported by that repo's ``ops/sweep.py``. When you change this file: edit here
first, then copy everything verbatim into every producer's ``ops/scanners.py``
(keep each file's own module docstring). Kept OUT of ``contract.py`` on purpose:
contract.py is pure stdlib envelope/ledger mechanics that shells out to nothing;
scanners invoke external tools, a different character.

Design (mirrors the review + STATUS-drift seams in sweep.py):
  - The load-bearing parsing is PURE and unit-tested: ``_gitleaks_findings`` /
    ``_pip_audit_findings`` / ``_npm_audit_findings`` map real tool output to
    candidate findings, exercised with captured fixtures (no tools needed).
  - The subprocess calls are thin seams (``run_gitleaks`` / ``run_pip_audit`` /
    ``run_npm_audit``) that return None on unavailable/unparseable so a broken
    scanner NEVER corrupts the ledger.
  - Applicability vs failure is the ``[]`` vs ``None`` distinction: a scanner
    whose manifest is absent is *not applicable* and returns ``[]``; a scanner
    that should have worked but didn't returns ``None``. On a FULL sweep a
    ``None`` (applicable-but-unavailable) aborts the write — never false-resolve
    that scanner's prior findings; in ``--diff`` a ``None`` is skipped.
  - A committed secret is NEVER written into the ledger: gitleaks findings carry
    only the rule id + file:line, never the matched value. pip-audit gives no
    CVSS, so dependency vulns default to "medium"; a leaked secret is "high".

Manifest locations are auto-detected so the module is repo-agnostic (byte-
identical vendoring): a Python manifest at repo root or under ``backend/``, a JS
lockfile at repo root or under ``frontend/``.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

# Where a Python requirements manifest / a JS lockfile may live, in priority
# order. Auto-detection keeps this module free of any one app's layout.
_PY_CANDIDATES = ("requirements.txt", "backend/requirements.txt")
_JS_CANDIDATES = ("package-lock.json", "frontend/package-lock.json")
# npm's four severities collapse onto the contract's three.
_NPM_SEVERITY = {"critical": "high", "high": "high", "moderate": "medium", "low": "low"}


# --- manifest detection ------------------------------------------------------


def find_py_manifest(repo: Path) -> str | None:
    """Repo-relative path of the Python requirements manifest, or None."""
    for c in _PY_CANDIDATES:
        if (Path(repo) / c).exists():
            return c
    return None


def find_js_lock(repo: Path) -> str | None:
    """Repo-relative path of the JS lockfile, or None."""
    for c in _JS_CANDIDATES:
        if (Path(repo) / c).exists():
            return c
    return None


def _is_manifest(path: str) -> bool:
    """Does a changed-file path look like a dependency manifest? (--diff gating —
    deps can't gain a vuln if no manifest moved.)"""
    return path.endswith(("requirements.txt", "package-lock.json", "package.json"))


# --- pure parsers (unit-tested against captured tool output) -----------------


def _rel(repo: Path, path: str) -> str:
    """A gitleaks File may be absolute (it echoes the scan root). Make it
    repo-relative for a stable, portable location/id."""
    try:
        return str(Path(path).resolve().relative_to(Path(repo).resolve()))
    except (ValueError, OSError):
        return path


def _gitleaks_findings(report: list, repo: Path) -> list[dict]:
    """Map a gitleaks JSON report (a list of leak objects) to candidate findings.
    Redacts by construction — only RuleID/File/StartLine reach the finding, never
    ``Secret``/``Match``. Collapses multiple leaks of the same rule in the same
    file to one id (line numbers shift; rule+file is the stable key)."""
    out: list[dict] = []
    seen: set = set()
    for r in report:
        if not isinstance(r, dict):
            continue
        rule, f = r.get("RuleID"), r.get("File")
        if not (isinstance(rule, str) and rule and isinstance(f, str) and f):
            continue
        rel = _rel(repo, f)
        fid = f"secret-{rule}-{rel}"
        if fid in seen:
            continue
        seen.add(fid)
        line = r.get("StartLine")
        loc = f"{rel}:{line}" if isinstance(line, int) else rel
        out.append({"id": fid, "severity": "high", "area": "security",
                    "headline": f"Possible committed secret ({rule}) in {rel} "
                                f"— rotate it and remove from the tree.",
                    "location": loc})
    return out


def _pip_audit_findings(report: dict, manifest: str) -> list[dict]:
    """Map pip-audit ``--format json`` output (``{"dependencies": [...]}``) to
    candidate findings — one per (package, vuln id). No CVSS in the payload, so
    severity defaults to medium."""
    out: list[dict] = []
    deps = report.get("dependencies") if isinstance(report, dict) else None
    for dep in deps or []:
        if not isinstance(dep, dict):
            continue
        name, ver = dep.get("name"), dep.get("version")
        if not isinstance(name, str) or not name:
            continue
        for v in dep.get("vulns") or []:
            if not isinstance(v, dict):
                continue
            vid = v.get("id")
            if not isinstance(vid, str) or not vid:
                continue
            fix = ", ".join(v.get("fix_versions") or []) or "no fix listed"
            out.append({"id": f"dep-pip-{name}-{vid}", "severity": "medium",
                        "area": "security",
                        "headline": f"{name} {ver} has known vulnerability {vid} "
                                    f"(fix: {fix}).",
                        "location": manifest})
    return out


def _npm_audit_findings(report: dict, manifest: str) -> list[dict]:
    """Map ``npm audit --json`` output (``{"vulnerabilities": {name: {...}}}``) to
    candidate findings — one per vulnerable package. npm's four severities map to
    the contract's three; the advisory title (when present in ``via``) sharpens
    the headline."""
    out: list[dict] = []
    vulns = report.get("vulnerabilities") if isinstance(report, dict) else None
    if not isinstance(vulns, dict):
        return out
    for name, info in vulns.items():
        if not isinstance(info, dict):
            continue
        sev = _NPM_SEVERITY.get(info.get("severity"), "medium")
        rng = info.get("range") or "?"
        title = None
        for via in info.get("via") or []:
            if isinstance(via, dict) and via.get("title"):
                title = via["title"]
                break
        detail = f" — {title}" if title else ""
        out.append({"id": f"dep-npm-{name}", "severity": sev, "area": "security",
                    "headline": f"npm dependency {name} {rng} has a {info.get('severity')} "
                                f"advisory{detail}.",
                    "location": manifest})
    return out


# --- subprocess seams (integration; return None on unavailable/unparseable) --


def _run_json_tool(cmd: list[str], cwd: Path, out_file: Path | None = None,
                   timeout: int = 300):
    """Run a scanner; return parsed JSON from ``out_file`` (or stdout) or None on
    any failure. Non-zero exit is NOT treated as failure on its own — scanners
    exit non-zero when they find something — so success is decided by "did we get
    parseable JSON", exactly like the review seam."""
    if shutil.which(cmd[0]) is None:
        return None
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                              timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    try:
        raw = out_file.read_text(encoding="utf-8") if out_file else proc.stdout
        return json.loads(raw)
    except (OSError, ValueError):
        return None


def run_gitleaks(repo: Path) -> list[dict] | None:
    """Scan the working tree for secrets (no git history — the conservative slice-1
    scope). None if gitleaks is missing or its report can't be parsed."""
    repo = Path(repo)
    with tempfile.NamedTemporaryFile(suffix=".json") as tf:
        report = _run_json_tool(
            ["gitleaks", "dir", ".", "--report-format", "json",
             "--report-path", tf.name, "--no-banner"],
            cwd=repo, out_file=Path(tf.name))
    if not isinstance(report, list):
        return None
    return _gitleaks_findings(report, repo)


def run_pip_audit(repo: Path) -> list[dict] | None:
    """Audit pinned Python deps. Returns [] (not None) when there is no manifest —
    the scanner is simply not applicable. None only when the tool is present-but-
    failed (e.g. an unresolvable pin) or missing."""
    repo = Path(repo)
    manifest = find_py_manifest(repo)
    if manifest is None:
        return []
    with tempfile.NamedTemporaryFile(suffix=".json") as tf:
        report = _run_json_tool(
            ["pip-audit", "-r", manifest, "--format", "json", "-o", tf.name],
            cwd=repo, out_file=Path(tf.name))
    if not isinstance(report, dict) or "dependencies" not in report:
        return None
    return _pip_audit_findings(report, manifest)


def run_npm_audit(repo: Path) -> list[dict] | None:
    """Audit JS deps. Returns [] when there is no lockfile (not applicable); None
    when npm is missing or its output can't be parsed. Runs in the lockfile's dir;
    the finding location points at the sibling package.json."""
    repo = Path(repo)
    lock = find_js_lock(repo)
    if lock is None:
        return []
    lock_dir = (repo / lock).parent
    manifest = str(Path(lock).parent / "package.json")
    report = _run_json_tool(["npm", "audit", "--json"], cwd=lock_dir)
    if not isinstance(report, dict) or "vulnerabilities" not in report:
        return None
    return _npm_audit_findings(report, manifest)


def run_security_scan(repo: Path, *, full_sweep: bool,
                      changed: set[str] | None = None) -> list[dict] | None:
    """Run the applicable deterministic scanners and return combined candidates.

    Secrets (gitleaks) always apply — a secret can land in any file. Dependency
    scans apply when their manifest exists; in --diff mode they're skipped unless
    a manifest changed (deps can't gain a vuln if they didn't move).

    On a FULL sweep, an applicable-but-unavailable scanner returns None from here
    — the caller aborts the write rather than let reconciliation false-resolve
    that scanner's prior findings. In --diff mode a failed scanner is skipped (no
    resolution happens there, so nothing to corrupt)."""
    repo = Path(repo)
    manifest_changed = changed is None or any(_is_manifest(f) for f in changed)
    steps = [run_gitleaks]
    if full_sweep or manifest_changed:
        steps += [run_pip_audit, run_npm_audit]
    combined: list[dict] = []
    for step in steps:
        res = step(repo)
        if res is None:
            if full_sweep:
                return None
            continue  # --diff: skip a broken/absent scanner
        combined.extend(res)
    return combined
