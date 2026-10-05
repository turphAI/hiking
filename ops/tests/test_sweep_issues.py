"""The hiking sweep is an Issue-record stamp writer (CONTRACT §12.5), like
every other swept producer: noticed for a new finding, `confirmed — held`
when the sweep stops seeing it."""
from ops import contract, sweep


def _ledger(repo, findings):
    (repo / "ops").mkdir(exist_ok=True)
    (repo / "_ops").mkdir(exist_ok=True)
    contract.write_ledger(repo / "ops" / "findings.json",
                          findings=findings, last_reviewed="2026-08-01")


def _cand(fid):
    return {"id": fid, "severity": "low", "area": "efficiency",
            "headline": "H", "location": "x.py:1"}


def _no_security(r, full_sweep, changed):
    return []


def test_sweep_writes_noticed_then_confirmed(tmp_path):
    _ledger(tmp_path, [])
    sweep.sweep(tmp_path, full_sweep=True, today="2026-10-11",
                review=lambda r, s: [_cand("new-b")], security=_no_security)
    (issue,) = contract.load_issue_store(tmp_path)["issues"]
    assert issue["id"] == "hiking:finding:new-b"
    assert [s["stamp"] for s in issue["history"]] == ["noticed"]

    sweep.sweep(tmp_path, full_sweep=True, today="2026-10-18",
                review=lambda r, s: [], security=_no_security)
    (issue,) = contract.load_issue_store(tmp_path)["issues"]
    assert [s["stamp"] for s in issue["history"]] == ["noticed", "confirmed"]
    assert issue["history"][-1]["how"] == "held"
