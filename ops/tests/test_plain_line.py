"""The code check's plain line (vantage theme 8 B5): the reviewer writes what goes
wrong for someone using the app, and only a plain line is kept."""
from ops import contract, sweep


def _cand(**extra):
    return {"id": "totals-off", "severity": "low", "area": "data_integrity",
            "headline": "parse_month_range drops the latest month", "location": "a.py:1", **extra}


def test_the_validator_keeps_a_plain_line():
    (c,) = sweep._validate_candidates([_cand(plain="Monthly totals can leave out the latest month.")])
    assert c["plain"] == "Monthly totals can leave out the latest month."


def test_the_validator_drops_a_line_that_isnt_plain():
    for bad in ("Your totals can be wrong.", "`months` is off by one.", None):
        (c,) = sweep._validate_candidates([_cand(plain=bad)])
        assert c["plain"] is None   # the finding stays; only the line goes


def test_the_prompt_asks_for_the_plain_line():
    assert '"plain"' in sweep.REVIEW_PROMPT and "no second person" in sweep.REVIEW_PROMPT


def test_the_reshaper_carries_the_lifecycle_and_the_plain_line():
    from ops import agent
    row = {"id": "a", "severity": "low", "area": "durability", "status": "wontfix",
           "headline": "h", "state": "accepted", "verdict_reason": "harmless",
           "verdict_at": "2026-10-10", "plain": "Totals can be wrong."}
    (f,) = agent.shape_findings([row])
    assert (f["state"], f["verdict_reason"], f["verdict_at"], f["plain"]) == (
        "accepted", "harmless", "2026-10-10", "Totals can be wrong.")
