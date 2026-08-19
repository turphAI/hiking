"""The Issue record — constructors, authority matrix, derivation, projections.

Conforms to CONTRACT.md §12 (spec: the vantage agent-legibility track's
ISSUE-SCHEMA). S0 stratum: spec + library only — nothing in the running system
emits or reads issues yet. The dispatcher and verifier become stamp writers in
S1; producers migrate in S2/S3, fed compatibility by the legacy projections at
the bottom of this file.

Design laws this module must not bend (S0 brief; breaks go back to the vantage
track as SCENARIOS run 4, never as local fixes):

1. History (the stamp sequence) is the only stored truth; where-it-stands is
   derived (``derive``), never written independently.
2. ``why`` is required on every stamp.
3. *approved* has no machine writer, ever; *came back* is human-writable.
4. "You" never appears in stored data — humans by id; second person is the
   renderer's job.
5. Two clocks: ``ours`` pauses while the governing human is away;
   ``the-world's`` never pauses and escalates instead.
6. Standing (``if_it_acts``, ``if_left_alone``) is altitude-invariant in every
   projection.
7. The participation boundary: an issue is work the system participates in;
   nothing here should make it easier to file work it doesn't.

Two validation layers, same division as ``attention.py``: the constructors
(``new_issue``, ``stamp_*``) raise ``ValueError`` at write time so a producer
can never build a malformed record; the ``*_violations`` functions report (list
of strings, ``[]`` when clean) so the manager's fold excludes invalid stamps
rather than TypeError-ing on them.

Vendorable: stdlib-only, imports nothing from ops_core — like ``contract.py``
it can be copied byte-identical into a producer when its stratum arrives.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# --- vocabulary (CONTRACT.md §12.1–§12.2) ------------------------------------

KINDS = ("finding", "drift", "heal", "decision", "claim")
SEVERITIES = ("low", "medium", "high")
AREAS = ("security", "durability", "data_integrity", "efficiency")
IF_IT_ACTS = ("one-way", "reversible", "read-only")
CLOCKS = ("ours", "the-world's")
SALIENCES = ("quiet", "normal", "now")
SPEAKS = ("asks", "tells", "quiet")
LINK_KINDS = ("blocks", "supersedes", "child-of")

STAMPS = ("noticed", "taken up", "brought to", "proposed", "worked",
          "approved", "confirmed", "closed", "came back")
CLOSED_HOWS = ("done", "accepted", "parked", "moot")
CONFIRMED_HOWS = ("held", "missed")

# Grace window after a default-motion auto-close (§12.4): an objection landing
# inside it reopens without ceremony. The window's length belongs to the
# standing rule that authorized the motion (rules are subjects, S8/S12); until
# rules are records (S1+) this constant is the placeholder default.
GRACE_WINDOW_DAYS = 3

# Law 4, mechanically enforced: second person never appears in stored prose.
_SECOND_PERSON = re.compile(r"\b(you|your|yours|yourself)\b", re.IGNORECASE)


# --- the authority matrix, as data (CONTRACT.md §12.3) ------------------------
# writer -> {stamp: allowed qualifiers (None = no qualifier constraint)}.
# Machine writers are rows; any ``by`` not in MACHINE_WRITERS is a human, whose
# authority is the HUMAN class row gated by per-domain standing in the registry.
# The *approved* column is categorical: it appears in no machine row, and no
# code path may add it — law 3.
#
# NOTE (flagged to vantage, SCENARIOS run 4 candidate): ISSUE-SCHEMA's matrix
# table gives "fixer / doctor" only *worked*, but its repo_health
# reconciliation — and its own born-closed example — require the repo-doctor to
# write noticed + worked + closed(done) in one pass. Implemented as the
# reconciliation requires; the table wants a row amendment.

AUTHORITY: dict[str, dict[str, tuple | None]] = {
    "sweep": {"noticed": None, "proposed": None, "confirmed": None,
              "closed": ("done", "moot"), "came back": None},
    "dispatcher": {"taken up": None, "brought to": None, "proposed": None},
    "fixer": {"worked": None},
    "repo-doctor": {"noticed": None, "worked": None, "closed": ("done",)},
    "verifier": {"confirmed": None, "closed": ("done",)},
    "manager": {"noticed": None, "brought to": None},  # noticed: about producers
}
MACHINE_WRITERS = frozenset(AUTHORITY)

# The human class row (symmetric matrix, run 3): humans take up and work like
# any fixer, approve (their column alone), confirm by observing, close only
# with a verdict qualifier, and contest machine truth via came back (S18).
HUMAN_AUTHORITY: dict[str, tuple | None] = {
    "noticed": None, "taken up": None, "worked": None, "approved": None,
    "confirmed": None, "closed": ("accepted", "parked"), "came back": None,
}


# --- the humans registry (CONTRACT.md §12.6) ----------------------------------

DEFAULT_REGISTRY_PATH = Path.home() / "Projects" / "_shared" / "humans.json"


def load_registry(path: Path | None = None) -> dict:
    """Read the humans registry (``~/Projects/_shared/humans.json``). Missing or
    malformed degrades to an empty registry rather than raising (§3.5) — a
    broken registry must not take the fold down; it just means no human stamp
    can validate until it's fixed."""
    p = Path(path) if path is not None else DEFAULT_REGISTRY_PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"humans": {}}
    if not isinstance(data, dict) or not isinstance(data.get("humans"), dict):
        return {"humans": {}}
    return data


def get_human(registry: dict, human_id: str) -> dict | None:
    """The registry entry for ``human_id``, or None when unregistered."""
    h = (registry.get("humans") or {}).get(human_id)
    return h if isinstance(h, dict) else None


def has_standing(registry: dict, human_id: str, domain: str) -> bool:
    """Whether this human holds standing in ``domain`` (ops · household ·
    health). Standing is what gates the human class row of the matrix."""
    h = get_human(registry, human_id)
    return bool(h) and domain in (h.get("standings") or [])


def is_away(registry: dict, human_id: str | None) -> bool:
    """The absence flag (S7). Unknown humans read as present — absence must be
    an affirmative fact, never a default."""
    h = get_human(registry, human_id) if human_id else None
    return bool(h) and h.get("presence") == "away"


def standing_holders(registry: dict, domain: str, *, exclude: tuple = (),
                     present_only: bool = False) -> list[str]:
    """Humans holding standing in ``domain``, registry order, minus
    ``exclude``. ``present_only`` filters out away humans — used to pick a
    re-route target for a world-clock escalation."""
    out = []
    for hid in (registry.get("humans") or {}):
        if hid in exclude or not has_standing(registry, hid, domain):
            continue
        if present_only and is_away(registry, hid):
            continue
        out.append(hid)
    return out


# --- stamp validation (fold-side: report, never raise) ------------------------


def _required_str(d: dict, key: str) -> bool:
    v = d.get(key)
    return isinstance(v, str) and bool(v.strip())


def stamp_violations(writer, stamp, *, registry: dict | None = None,
                     domain: str = "ops") -> list[str]:
    """Violations for one History stamp written by ``writer`` (the stamp's
    ``by``), ``[]`` when it conforms. Same contract as ``attention.py``'s
    ``item_violations``: the fold reports and excludes, nothing TypeErrors.

    Checks shape (why on every stamp; qualifiers on closed/confirmed; ``to`` on
    brought to; ``as`` on approved) and authority (the matrix for machine
    writers; registry standing in ``domain``, plus a known ``as`` role, for
    humans). Without a ``registry`` the human membership/standing/role checks
    are skipped — that half of the matrix lives at the fold, where the registry
    is in hand."""
    if not isinstance(stamp, dict):
        return ["stamp: not an object"]
    name = stamp.get("stamp")
    where = f"stamp {name!r}" if isinstance(name, str) else "stamp"
    errs = []
    if name not in STAMPS:
        errs.append(f"{where}: unknown stamp {name!r}")
        return errs
    if not isinstance(writer, str) or not writer:
        errs.append(f"{where}: by missing")
    if not _required_str(stamp, "why"):
        errs.append(f"{where}: why missing — a stamp without a why is a "
                    "contract violation")
    if not _required_str(stamp, "at"):
        errs.append(f"{where}: at missing")
    how = stamp.get("how")
    if name == "closed" and how not in CLOSED_HOWS:
        errs.append(f"{where}: closed must be qualified — how {how!r} not in "
                    f"{'/'.join(CLOSED_HOWS)}")
    if name == "confirmed" and how not in CONFIRMED_HOWS:
        errs.append(f"{where}: confirmed must be qualified — how {how!r} not "
                    f"in {'/'.join(CONFIRMED_HOWS)}")
    if name not in ("closed", "confirmed") and how is not None:
        errs.append(f"{where}: how is only valid on closed/confirmed")
    if name == "brought to" and not _required_str(stamp, "to"):
        errs.append(f"{where}: to missing — brought to names the human asked")
    if name == "approved" and not _required_str(stamp, "as"):
        errs.append(f"{where}: as missing — signing as CEO and signing as "
                    "engineer are different acts")
    refs = stamp.get("refs")
    if refs is not None and not (isinstance(refs, list)
                                 and all(isinstance(r, str) for r in refs)):
        errs.append(f"{where}: refs must be a list of strings")
    cost = stamp.get("cost")
    if cost is not None and (isinstance(cost, bool)
                             or not isinstance(cost, (int, float))):
        errs.append(f"{where}: cost must be a number")
    why = stamp.get("why")
    if isinstance(why, str) and _SECOND_PERSON.search(why):
        errs.append(f"{where}: second person in why — humans by id; \"you\" "
                    "is the renderer's job")

    # -- authority --
    if not isinstance(writer, str) or not writer:
        return errs
    if writer in MACHINE_WRITERS:
        allowed = AUTHORITY[writer]
        if name == "approved":
            errs.append(f"{where}: approved has no machine writer — "
                        f"{writer} may never pass the human gate")
        elif name not in allowed:
            errs.append(f"{where}: {writer} may not write {name!r}")
        elif allowed[name] is not None and how not in allowed[name]:
            errs.append(f"{where}: {writer} may close only as "
                        f"{'/'.join(allowed[name])}, not {how!r}")
    else:
        if name not in HUMAN_AUTHORITY:
            errs.append(f"{where}: a human may not write {name!r}")
        elif (HUMAN_AUTHORITY[name] is not None
              and how not in HUMAN_AUTHORITY[name]):
            errs.append(f"{where}: a human may close only as "
                        f"{'/'.join(HUMAN_AUTHORITY[name])}, not {how!r}")
        if registry is not None:
            if get_human(registry, writer) is None:
                errs.append(f"{where}: unknown human {writer!r} — not in the "
                            "registry")
            elif not has_standing(registry, writer, domain):
                errs.append(f"{where}: {writer} holds no {domain} standing")
            else:
                hat = stamp.get("as")
                roles = (get_human(registry, writer) or {}).get("roles") or []
                if hat is not None and hat not in roles:
                    errs.append(f"{where}: unknown role {hat!r} for {writer}")
    return errs


# --- stamp constructors (writer-side: raise) ----------------------------------


def _stamp(name: str, *, by: str, why: str, at: str | None = None,
           as_: str | None = None, refs: list[str] | None = None,
           cost: float | None = None, **extra) -> dict:
    st = {"stamp": name, "at": at or _now_iso(), "by": by}
    if as_ is not None:
        st["as"] = as_
    st["why"] = why
    for k, v in extra.items():
        if v is not None:
            st[k] = v
    if refs is not None:
        st["refs"] = list(refs)
    if cost is not None:
        st["cost"] = cost
    errs = stamp_violations(by, st)
    if errs:
        raise ValueError("; ".join(errs))
    return st


def _now_iso() -> str:
    return (datetime.now(timezone.utc).astimezone()
            .isoformat(timespec="seconds"))


def stamp_noticed(*, by, why, at=None, as_=None, refs=None, cost=None) -> dict:
    """The matter came into existence; creates the issue (always first)."""
    return _stamp("noticed", by=by, why=why, at=at, as_=as_, refs=refs,
                  cost=cost)


def stamp_taken_up(*, by, why, at=None, as_=None, refs=None,
                   cost=None) -> dict:
    """Someone committed to act — an agent under a standing rule, or a human
    claiming their own work (run 3)."""
    return _stamp("taken up", by=by, why=why, at=at, as_=as_, refs=refs,
                  cost=cost)


def stamp_brought_to(*, to, by, why, at=None, as_=None, refs=None,
                     cost=None) -> dict:
    """Presented as a question to ``to``, the human holding standing. History
    records the ask truthfully; the renderer re-resolves the addressee at read
    time (``derive``)."""
    return _stamp("brought to", by=by, why=why, at=at, as_=as_, refs=refs,
                  cost=cost, to=to)


def stamp_proposed(*, by, why, at=None, as_=None, refs=None,
                   cost=None) -> dict:
    """\"Recommend closing as-is; closes itself {when} unless overridden.\""""
    return _stamp("proposed", by=by, why=why, at=at, as_=as_, refs=refs,
                  cost=cost)


def stamp_worked(*, by, why, at=None, as_=None, refs=None, cost=None) -> dict:
    """The substantive act done — refs carry the proof (provenance is
    positional). Surface verb may specialize (fixed, bumped, wrote, called)."""
    return _stamp("worked", by=by, why=why, at=at, as_=as_, refs=refs,
                  cost=cost)


def stamp_approved(*, by, as_, why, at=None, refs=None, cost=None) -> dict:
    """The human gate passed. Humans only, ever (law 3); ``as_`` (the hat) is
    required — a machine ``by`` raises here and is a violation at the fold."""
    return _stamp("approved", by=by, why=why, at=at, as_=as_, refs=refs,
                  cost=cost)


def stamp_confirmed(*, how, by, why, at=None, as_=None, refs=None,
                    cost=None) -> dict:
    """The claim's test resolved; ``how`` is ``held`` or ``missed``. The
    consequence is kind-derived and asymmetric: a fix that misses comes back; a
    claim that misses closes — a labeled data point for the ledger."""
    return _stamp("confirmed", by=by, why=why, at=at, as_=as_, refs=refs,
                  cost=cost, how=how)


def stamp_closed(*, how, by, why, at=None, as_=None, refs=None,
                 cost=None) -> dict:
    """Terminal, always qualified: ``how`` ∈ done · accepted · parked · moot.
    ``why`` carries the verdict reason for accepted/parked."""
    return _stamp("closed", by=by, why=why, at=at, as_=as_, refs=refs,
                  cost=cost, how=how)


def stamp_came_back(*, by, why, at=None, as_=None, refs=None,
                    cost=None) -> dict:
    """It re-surfaced; reopens the same issue — the thread of truth doesn't
    fragment. Human-writable (S18): machine truth must be contestable by the
    humans it serves."""
    return _stamp("came back", by=by, why=why, at=at, as_=as_, refs=refs,
                  cost=cost)


# --- the record ---------------------------------------------------------------


def issue_violations(issue, *, registry: dict | None = None,
                     domain: str = "ops", where: str = "issue") -> list[str]:
    """Violations for one issue record, ``[]`` when it conforms. Fold-side
    (report, never raise); the manager excludes a malformed issue from the fold
    and surfaces the violation, same as a malformed attention item today."""
    if not isinstance(issue, dict):
        return [f"{where}: not an object"]
    errs = []
    iid = issue.get("id")
    parts = iid.split(":") if isinstance(iid, str) else []
    if len(parts) < 3 or not all(parts):
        errs.append(f"{where}: id must be <scope>:<kind>:<semantic> (§3.3)")
    kind = issue.get("kind")
    if kind not in KINDS:
        errs.append(f"{where}: kind {kind!r} not in {'/'.join(KINDS)}")
    elif len(parts) >= 3 and all(parts) and parts[1] != kind:
        errs.append(f"{where}: id kind segment {parts[1]!r} != kind {kind!r}")
    if issue.get("severity") not in SEVERITIES:
        errs.append(f"{where}: severity {issue.get('severity')!r} not in "
                    f"{'/'.join(SEVERITIES)}")
    area = issue.get("area")
    if area is not None and area not in AREAS:
        errs.append(f"{where}: area {area!r} not in {'/'.join(AREAS)}")

    subject = issue.get("subject")
    if not isinstance(subject, dict) or not _required_str(subject, "what"):
        errs.append(f"{where}: subject.what missing")
    else:
        loc = subject.get("where")
        loc_ok = isinstance(loc, str) or (
            isinstance(loc, list) and loc
            and all(isinstance(s, str) for s in loc))
        if not loc_ok:
            errs.append(f"{where}: subject.where must be a locator or a list "
                        "of locators")
        elif parts and parts[0] == "suite" and not isinstance(loc, list):
            errs.append(f"{where}: a suite: issue is fleet-scoped — "
                        "subject.where must be a list, one locator per repo "
                        "(S17)")

    standing = issue.get("standing")
    if not isinstance(standing, dict):
        errs.append(f"{where}: standing missing")
        standing = {}
    if "where" in standing:
        errs.append(f"{where}: standing.where is derived from History, never "
                    "stored (law 1)")
    acting = standing.get("acting_under")
    if not (acting in ("human-approval", "full-autonomy")
            or (isinstance(acting, str)
                and acting.startswith("standing-rule:")
                and len(acting) > len("standing-rule:"))):
        errs.append(f"{where}: acting_under {acting!r} must be human-approval "
                    "| standing-rule:<ref> | full-autonomy")
    if acting == "human-approval" and not _required_str(standing, "whose"):
        errs.append(f"{where}: standing.whose required under human-approval")
    if standing.get("if_it_acts") not in IF_IT_ACTS:
        errs.append(f"{where}: if_it_acts {standing.get('if_it_acts')!r} not "
                    f"in {'/'.join(IF_IT_ACTS)}")
    ila = standing.get("if_left_alone")
    if ila is not None:
        if not isinstance(ila, dict) or not _required_str(ila, "outcome"):
            errs.append(f"{where}: if_left_alone.outcome missing")
        else:
            clock = ila.get("clock")
            if ila.get("when") is not None and clock not in CLOCKS:
                errs.append(f"{where}: if_left_alone.when is set — clock "
                            f"required ({' | '.join(CLOCKS)})")
            if clock is not None and clock not in CLOCKS:
                errs.append(f"{where}: clock {clock!r} not in "
                            f"{' | '.join(CLOCKS)}")
            if kind == "claim" and clock is not None:
                errs.append(f"{where}: claims use neither clock — they "
                            "resolve by observation (run 2)")

    moment = issue.get("moment")
    if not isinstance(moment, dict):
        errs.append(f"{where}: moment missing")
        moment = {}
    if moment.get("salience") not in SALIENCES:
        errs.append(f"{where}: salience {moment.get('salience')!r} not in "
                    f"{'/'.join(SALIENCES)}")
    speaks = moment.get("speaks")
    if speaks is not None and speaks not in SPEAKS:
        errs.append(f"{where}: speaks {speaks!r} not in {'/'.join(SPEAKS)}")
    if speaks == "asks" and not _required_str(moment, "whom"):
        errs.append(f"{where}: moment.whom required when speaks is asks")

    account = issue.get("account")
    if not isinstance(account, dict) or not _required_str(account, "headline"):
        errs.append(f"{where}: account.headline missing (§3.4)")
        account = account if isinstance(account, dict) else {}
    for k in ("headline", "plain"):
        v = account.get(k)
        if isinstance(v, str) and _SECOND_PERSON.search(v):
            errs.append(f"{where}: second person in account.{k} — humans by "
                        "id; \"you\" is the renderer's job (law 4)")

    playbook = issue.get("playbook")
    if playbook is not None and not (
            isinstance(playbook, list)
            and all(isinstance(s, str) for s in playbook)):
        errs.append(f"{where}: playbook must be a list of strings")
    links = issue.get("links")
    if links is not None:
        if not isinstance(links, list):
            errs.append(f"{where}: links must be a list")
        else:
            for i, ln in enumerate(links):
                if not (isinstance(ln, dict) and ln.get("kind") in LINK_KINDS
                        and _required_str(ln, "issue")):
                    errs.append(f"{where}: links[{i}] must be {{kind: "
                                f"{'|'.join(LINK_KINDS)}, issue: <id>}}")
    if domain in ("household", "health") and not issue.get("audience"):
        errs.append(f"{where}: audience required on {domain}-domain issues "
                    "before any rendering (run 3 — privacy, not a gap)")

    history = issue.get("history")
    if not (isinstance(history, list) and history):
        errs.append(f"{where}: history missing — History is the only stored "
                    "truth (law 1)")
        history = []
    elif not (isinstance(history[0], dict)
              and history[0].get("stamp") == "noticed"):
        errs.append(f"{where}: history must begin with noticed — the stamp "
                    "that creates the issue")
    for i, st in enumerate(history):
        by = st.get("by") if isinstance(st, dict) else None
        errs.extend(f"{where}: history[{i}] {e}" for e in stamp_violations(
            by, st, registry=registry, domain=domain))
    return errs


def new_issue(issue_id: str, *, kind: str, severity: str, subject: dict,
              standing: dict, account: dict, history: list[dict],
              area: str | None = None, audience: str | None = None,
              salience: str = "normal", playbook: list[str] | None = None,
              links: list[dict] | None = None) -> dict:
    """Build a full issue record, raising ``ValueError`` unless it conforms.

    History is passed whole (built from the ``stamp_*`` constructors) and must
    begin with *noticed* — an issue exists because something was noticed, never
    otherwise. ``moment.speaks``/``moment.whom`` are NOT parameters: they are
    derived from History and cached here (law 1 — same answer as any consumer
    recomputing via ``derive``, by construction). ``standing`` likewise must
    not carry ``where``."""
    speaks, whom = _speaks_from_history(standing, history)
    moment = {"speaks": speaks}
    if whom is not None:
        moment["whom"] = whom
    moment["salience"] = salience
    issue = {"id": issue_id, "kind": kind}
    if area is not None:
        issue["area"] = area
    issue["severity"] = severity
    issue["subject"] = dict(subject)
    issue["standing"] = dict(standing)
    issue["moment"] = moment
    if audience is not None:
        issue["audience"] = audience
    issue["account"] = dict(account)
    if playbook is not None:
        issue["playbook"] = list(playbook)
    if links is not None:
        issue["links"] = [dict(ln) for ln in links]
    issue["history"] = [dict(st) for st in history]
    errs = issue_violations(issue)
    if errs:
        raise ValueError("; ".join(errs))
    return issue


# --- derivation (CONTRACT.md §12.4) -------------------------------------------
# One derivation function, owned here: producers cache its output, consumers
# recompute it — same answer by construction (the open question's resolution).


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _speaks_from_history(standing: dict, history: list) -> tuple[str, str | None]:
    """``moment.speaks`` = f(stamps): an unresolved *brought to* → asks (whom =
    its addressee); closed → quiet; full-autonomy → quiet; otherwise recent
    activity is a standing rule or a human at work → tells."""
    last = history[-1] if history and isinstance(history[-1], dict) else {}
    name = last.get("stamp")
    if name == "brought to":
        return "asks", last.get("to")
    if name == "closed":
        return "quiet", None
    if isinstance(standing, dict) \
            and standing.get("acting_under") == "full-autonomy":
        return "quiet", None
    return "tells", None


def derive(issue: dict, now, registry: dict | None = None, *,
           domain: str = "ops") -> dict:
    """Derived state for one issue at time ``now`` (ISO string, date, or
    datetime): ``where`` (standing), ``speaks``/``whom`` (moment), effective
    ``salience``, plus ``clock`` and ``grace`` state. Never stored back except
    as a cache — History stays the only truth (law 1); any stored
    ``standing.where`` is ignored here and flagged by ``issue_violations``.

    Owns the three read-time rules: **addressee re-resolution** (S16 — an ask
    re-routes when its addressee's standing is gone, and says so), the **two
    clocks** (S7/run 3 — ``ours`` pauses while the governing human is away;
    ``the-world's`` never pauses: salience rises and the ask re-routes to
    another present holder of standing), and the **grace window** (S6 — a
    machine auto-close after a *proposed* stays reopenable without ceremony for
    a few days)."""
    now_d = _as_date(now)
    standing = issue.get("standing") or {}
    moment = issue.get("moment") or {}
    history = [st for st in (issue.get("history") or [])
               if isinstance(st, dict) and st.get("stamp") in STAMPS]
    last = history[-1] if history else {}
    name = last.get("stamp")
    last_d = _as_date(last.get("at"))

    speaks, whom = _speaks_from_history(standing, history)
    salience = moment.get("salience") or "normal"
    notes: list[str] = []

    # Addressee re-resolution (S16): history said "brought to X" truthfully,
    # but the ask belongs to whoever holds standing NOW.
    if whom is not None and registry is not None \
            and not has_standing(registry, whom, domain):
        holders = standing_holders(registry, domain, exclude=(whom,))
        if holders:
            notes.append(f"re-routed from {whom} — no current {domain} "
                         "standing")
            whom = holders[0]
        else:
            notes.append(f"{whom} no longer holds {domain} standing and no "
                         "other holder exists")

    # The two clocks (law 5).
    ila = standing.get("if_left_alone") or {}
    clock_kind = ila.get("clock") if isinstance(ila, dict) else None
    governing = standing.get("whose") or whom
    clock = None
    if clock_kind in CLOCKS:
        away = registry is not None and is_away(registry, governing)
        if clock_kind == "ours":
            clock = {"kind": "ours", "paused": away}
            if away:
                notes.append(f"paused — {governing} is away; absence is "
                             "never consent")
        else:
            clock = {"kind": "the-world's", "paused": False,
                     "escalated": away, "rerouted_to": None}
            if away:
                salience = "now"
                others = standing_holders(registry, domain,
                                          exclude=(governing,),
                                          present_only=True)
                if others:
                    clock["rerouted_to"] = others[0]
                    if speaks == "asks":
                        whom = others[0]
                    notes.append(f"{governing} is away and the world's clock "
                                 f"does not pause — escalated to {others[0]}")
                else:
                    notes.append(f"{governing} is away and the world's clock "
                                 "does not pause — no other holder of "
                                 f"{domain} standing to escalate to")

    # where = f(last stamp).
    paused = bool(clock and clock.get("paused"))
    if name in (None, "noticed"):
        where_s = "open, not yet taken up"
    elif name == "taken up":
        where_s = "in hand"
    elif name == "brought to":
        days = (now_d - last_d).days if now_d and last_d else None
        age = f" ({days}d)" if days is not None and days >= 0 else ""
        where_s = f"waiting on {whom}{age}"
    elif name == "proposed":
        when = ila.get("when") if isinstance(ila, dict) else None
        where_s = (f"closing itself {when} unless overridden" if when
                   else "closing itself unless overridden")
        if paused:
            where_s = f"proposed — the clock is paused while {governing} " \
                      "is away"
    elif name in ("worked", "approved"):
        where_s = "awaiting confirmation"
    elif name == "confirmed":
        where_s = f"confirmed — {last.get('how')}"
    elif name == "closed":
        where_s = f"closed — {last.get('how')}"
    else:  # came back
        where_s = "open again"
    if name == "brought to" and paused:
        where_s += f" — paused, {governing} is away"
    for n in notes:
        if n.startswith("re-routed"):
            where_s += f" — {n}"

    # Grace window (S6): only a machine's default-motion close (a *proposed*
    # earlier in History) gets one; a human's verdict close is ordinary.
    grace = None
    if name == "closed" and last.get("by") in MACHINE_WRITERS \
            and any(st.get("stamp") == "proposed" for st in history[:-1]) \
            and now_d and last_d:
        until = last_d + timedelta(days=GRACE_WINDOW_DAYS)
        if now_d <= until:
            grace = {"reopen_until": until.isoformat()}

    out = {"where": where_s, "speaks": speaks, "whom": whom,
           "salience": salience, "clock": clock, "grace": grace}
    if notes:
        out["notes"] = notes
    return out


# --- legacy projections (CONTRACT.md §12.7) -----------------------------------
# The compatibility promise S2/S3 depend on: old consumers can be fed from the
# new record on day one, so nothing has to migrate before its stratum. Standing
# is altitude-invariant (law 6): neither projection ever simplifies away
# if_it_acts / if_left_alone — the attention projection carries the headline
# (account altitude); blast radius questions go to the record itself.

# last stamp -> (§4.7 status, §4.7 state or None-to-omit). Must stay coherent
# with contract.py's status_for_state pairing.
_FINDING_STATE = {
    "noticed": ("open", None),
    "taken up": ("open", "fix_in_flight"),
    "brought to": ("open", None),
    "proposed": ("open", None),
    "worked": ("open", "resolved_pending_verify"),
    "approved": ("open", "resolved_pending_verify"),
    "came back": ("open", None),
}


def to_quality_finding(issue: dict) -> dict:
    """Project an issue into a §4.7 quality finding — the shape
    ``contract.make_finding`` builds and today's ledgers/consumers read.
    Lossy by design (History collapses to status/state; the projection is for
    consumers that predate History): id keeps the semantic tail, status/state
    come from the last stamp, ``fix_ref`` from the last *worked* stamp's refs,
    ``sweep_id`` from a ``sweep:`` ref on *noticed*, verdict fields from a
    human's accepted/parked close. ``closed — moot`` maps to bare ``wontfix``
    (no legacy state carries moot)."""
    history = [st for st in (issue.get("history") or [])
               if isinstance(st, dict)]
    last = history[-1] if history else {}
    name, how = last.get("stamp"), last.get("how")
    if name == "closed":
        status, state = {"done": ("resolved", "resolved"),
                         "accepted": ("wontfix", "accepted"),
                         "parked": ("wontfix", "parked"),
                         "moot": ("wontfix", None)}.get(how, ("open", None))
    elif name == "confirmed":
        status, state = (("resolved", "resolved") if how == "held"
                         else ("open", None))
    else:
        status, state = _FINDING_STATE.get(name, ("open", None))

    noticed = history[0] if history else {}
    worked = [st for st in history if st.get("stamp") == "worked"]
    fix_ref = None
    if worked and worked[-1].get("refs"):
        fix_ref = worked[-1]["refs"][0]
    sweep_id = next((r[len("sweep:"):] for r in (noticed.get("refs") or [])
                     if isinstance(r, str) and r.startswith("sweep:")), None)
    loc = (issue.get("subject") or {}).get("where")
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    verdict_reason = verdict_at = None
    if status == "wontfix":
        verdict_reason, verdict_at = last.get("why"), _date_str(last.get("at"))

    f = {
        "id": issue.get("id", "").split(":", 2)[-1],
        "severity": issue.get("severity"),
        "area": issue.get("area"),
        "status": status,
        "headline": (issue.get("account") or {}).get("headline"),
        "location": loc,
        "first_seen": _date_str(noticed.get("at")),
        "resolved_at": _date_str(last.get("at")) if status == "resolved"
        else None,
        "detail_url": None,
    }
    for k, v in (("state", state), ("fix_ref", fix_ref),
                 ("verdict_reason", verdict_reason), ("verdict_at", verdict_at),
                 ("sweep_id", sweep_id)):
        if v is not None:
            f[k] = v
    return f


def _date_str(at) -> str | None:
    d = _as_date(at)
    return d.isoformat() if d else None


def to_attention_item(issue: dict) -> dict | None:
    """Project an issue into a §4.4 attention item, or None when it speaks
    ``quiet`` — the legacy queue IS ``speaks != quiet`` (the authored list is
    gone). Salience maps onto priority (quiet→0, normal→1, now→2 — the
    presentation half of the old field; severity stays on the record). The
    item id is the full issue id — already ``<app>:``-prefixed per §3.3, so
    the manager's fold dedupes unchanged. The playbook rides along as
    ``instructions``."""
    speaks, _whom = _speaks_from_history(issue.get("standing") or {},
                                         issue.get("history") or [])
    if speaks == "quiet":
        return None
    moment = issue.get("moment") or {}
    history = issue.get("history") or []
    noticed = history[0] if history and isinstance(history[0], dict) else {}
    item = {
        "id": issue.get("id"),
        "priority": {"quiet": 0, "normal": 1, "now": 2}.get(
            moment.get("salience"), 1),
        "headline": (issue.get("account") or {}).get("headline"),
        "detail_url": None,
        "created_at": noticed.get("at"),
    }
    if issue.get("playbook"):
        item["instructions"] = list(issue["playbook"])
    return item
