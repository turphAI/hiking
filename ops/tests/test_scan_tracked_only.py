"""The secret scan sees every file git doesn't ignore, as it is on disk (2026-10-11):
gitignored runtime data on the mini (secrets.env, message stores) never reaches
GitHub, so it isn't a leak; an unstaged edit or a new file could, so it's scanned."""
import shutil
import subprocess

import pytest

from ops import scanners


def _repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("data/\n")
    (tmp_path / "app.py").write_text("print('hi')\n")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "secrets.env").write_text("TOKEN=x\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    return tmp_path


def test_only_tracked_files_are_handed_to_gitleaks(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    seen = {}

    def fake_tool(cmd, cwd, out_file=None, timeout=300):
        seen["files"] = sorted(str(p.relative_to(cwd)) for p in cwd.rglob("*") if p.is_file())
        return []

    monkeypatch.setattr(scanners.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(scanners, "_run_json_tool", fake_tool)
    assert scanners.run_gitleaks(repo) == []
    assert seen["files"] == [".gitignore", "app.py"]   # data/secrets.env never scanned


def test_unstaged_edits_and_new_unignored_files_are_scanned(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    (repo / "app.py").write_text("print('edited, not staged')\n")
    (repo / "new.py").write_text("x = 1\n")
    seen = {}

    def fake_tool(cmd, cwd, out_file=None, timeout=300):
        seen["files"] = {str(p.relative_to(cwd)): p.read_text() for p in cwd.rglob("*") if p.is_file()}
        return []

    monkeypatch.setattr(scanners.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(scanners, "_run_json_tool", fake_tool)
    scanners.run_gitleaks(repo)
    assert seen["files"]["app.py"] == "print('edited, not staged')\n"   # the disk, not the index
    assert "new.py" in seen["files"] and "data/secrets.env" not in seen["files"]


@pytest.mark.skipif(shutil.which("gitleaks") is None, reason="gitleaks not installed")
def test_a_real_scan_flags_a_tracked_secret_and_not_an_ignored_one(tmp_path):
    repo = _repo(tmp_path)
    key = "ghp_" + "Ab1Cd2Ef3Gh4Ij5Kl6Mn7Op8Qr9St0Uv1Wx2"
    (repo / "data" / "secrets.env").write_text(f"GITHUB_TOKEN={key}\n")
    (repo / "leak.py").write_text(f'TOKEN = "{key}"\n')   # new, not yet added: still scanned
    ids = [f["id"] for f in scanners.run_gitleaks(repo)]
    assert ids and all(i.endswith("-leak.py") for i in ids), ids
