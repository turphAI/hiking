"""Tests for the hiking-ops adapter: health + ledger -> quality.json.

The quality.json tests are boilerplate shared across every producer in the
suite. test_build_health_minimal_runless matches agent.py's runless pattern
(hiking is interactive, like witness — no batch runs to report).
"""
import json
from pathlib import Path

from ops import agent


def _write_ledger(tmp_path: Path, payload: dict) -> None:
    (tmp_path / "ops").mkdir(parents=True, exist_ok=True)
    (tmp_path / "ops" / "findings.json").write_text(json.dumps(payload), encoding="utf-8")


# --- health -------------------------------------------------------------


def test_build_health_minimal_runless(tmp_path: Path):
    agent.build_health(tmp_path)
    h = json.loads((tmp_path / "_ops" / "health.json").read_text())
    assert h["app"] == agent.APP
    assert h["last_run"] is None
    assert h["next_run"] is None
    assert h["warnings"] == []


def test_build_topology_declares_node(tmp_path: Path):
    agent.build_topology(tmp_path)
    t = json.loads((tmp_path / "_ops" / "topology.json").read_text())
    assert t["app"] == agent.APP
    assert t["node"]["id"] == agent.APP


# --- quality (CONTRACT.md §4.7) — shared shape across every producer ----


def test_build_quality_from_ledger(tmp_path: Path):
    _write_ledger(tmp_path, {
        "last_reviewed": "2026-06-07",
        "findings": [
            {"id": "a", "severity": "low", "area": "security", "status": "open",
             "headline": "A"},
            {"id": "b", "severity": "high", "area": "durability", "status": "resolved",
             "headline": "B", "resolved_at": "2026-06-07"},
        ],
    })
    payload = agent.build_quality(tmp_path)
    assert (tmp_path / "_ops" / "quality.json").is_file()
    assert payload["app"] == agent.APP
    assert payload["last_reviewed"] == "2026-06-07"
    assert payload["summary"] == {"open": 1, "resolved": 1,
                                  "by_severity": {"high": 0, "medium": 0, "low": 1}}


def test_build_quality_missing_ledger_degrades_to_empty(tmp_path: Path):
    payload = agent.build_quality(tmp_path)
    assert payload["findings"] == []
    assert payload["last_reviewed"] is None


def test_build_quality_malformed_ledger_degrades_to_empty(tmp_path: Path):
    (tmp_path / "ops").mkdir(parents=True, exist_ok=True)
    (tmp_path / "ops" / "findings.json").write_text("{not json", encoding="utf-8")
    assert agent.build_quality(tmp_path)["findings"] == []


def test_build_quality_skips_bad_rows(tmp_path: Path):
    _write_ledger(tmp_path, {"findings": [
        {"id": "good", "severity": "low", "area": "security", "status": "open",
         "headline": "ok"},
        {"id": "bad-sev", "severity": "nope", "area": "security", "status": "open",
         "headline": "x"},
        {"id": "bad-area", "severity": "low", "area": "vibes", "status": "open",
         "headline": "x"},
        {"id": "", "severity": "low", "area": "security", "status": "open",
         "headline": "x"},
        "not-a-dict",
    ]})
    assert [f["id"] for f in agent.build_quality(tmp_path)["findings"]] == ["good"]


def test_seed_ledger_is_valid():
    """The committed ops/findings.json must survive shape_findings — guards
    against a typo in the seed silently dropping real findings."""
    project_root = Path(__file__).resolve().parents[2]
    ledger = project_root / "ops" / "findings.json"
    if not ledger.is_file():
        return  # no seed committed yet
    raw, _ = agent.load_ledger(ledger)
    assert len(agent.shape_findings(raw)) == len(raw)
