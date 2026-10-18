"""run_review runs on a copy holding only in-scope code, never on the repo
(sweep-review-no-data-dir-enforcement across the suite)."""
import json
import subprocess
from pathlib import Path

from ops import sweep
from ops_core import review_sandbox


def _repo(tmp_path):
    repo = tmp_path / "repo"
    expected = []
    for d in sweep._SCOPE_DIRS:
        (repo / d).mkdir(parents=True, exist_ok=True)
        (repo / d / "mod.py").write_text("# code")
        expected.append(d + "mod.py")
    for f in getattr(sweep, "_SCOPE_FILES", set()):
        (repo / f).parent.mkdir(parents=True, exist_ok=True)
        (repo / f).write_text("# code")
        expected.append(f)
    out = sorted(sweep._SCOPE_DIRS)[0]
    (repo / out / "tests").mkdir(parents=True, exist_ok=True)
    (repo / out / "tests" / "test_x.py").write_text("# test, out of scope")
    (repo / "data").mkdir()
    (repo / "data" / "private.db").write_bytes(b"PRIVATE")
    (repo / "data" / "secret.key").write_text("TOP-SECRET")
    (repo / ".env").write_text("API_KEY=x")
    return repo, sorted(set(expected))


def _spy(monkeypatch):
    seen = {}
    real_run = subprocess.run

    def fake_run(cmd, cwd=None, **kw):
        if cmd[0] != "claude":      # the sandbox also shells out to git to list tracked files
            return real_run(cmd, cwd=cwd, **kw)
        seen["cwd"] = cwd
        seen["files"] = sorted(str(p.relative_to(cwd)) for p in Path(cwd).rglob("*") if p.is_file())
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"result": "[]"}), "")

    monkeypatch.setattr(sweep.shutil, "which", lambda name: "/usr/bin/claude")
    monkeypatch.setattr(review_sandbox.subprocess, "run", fake_run)
    return seen


def test_full_review_sees_only_in_scope_code_never_data_or_secrets(tmp_path, monkeypatch):
    repo, expected = _repo(tmp_path)
    seen = _spy(monkeypatch)
    assert sweep.run_review(repo, None) == []
    assert seen["files"] == expected                 # no data/, no .env, no tests
    assert Path(seen["cwd"]) != repo and not Path(seen["cwd"]).exists()


def test_diff_review_sees_only_the_changed_files(tmp_path, monkeypatch):
    repo, expected = _repo(tmp_path)
    seen = _spy(monkeypatch)
    sweep.run_review(repo, expected[:1])
    assert seen["files"] == expected[:1]
