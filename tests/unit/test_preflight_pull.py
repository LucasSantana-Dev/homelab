"""Tests for scripts/deployment/preflight-pull.sh.

On 2026-09-27, `git pull` stopped halfway through a manual deploy: some
tracked dirs (observability/, tailscale/, a few files) were root-owned, git
hit "unable to unlink old ... Permission denied", and HEAD stayed on the old
commit while ~22 files were already overwritten. This script is meant to
catch that class of failure (unwritable tracked file/dir, or a dirty tracked
file) before `git pull` ever runs.
"""

import os
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "deployment" / "preflight-pull.sh"


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)


def _run(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def test_passes_on_clean_writable_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "config.yml").write_text("a: 1\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "writable" in result.stdout


def test_fails_on_dirty_tracked_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "config.yml").write_text("a: 1\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

    (repo / "config.yml").write_text("a: 2\n")

    result = _run(repo)
    assert result.returncode == 1, result.stdout
    assert "local modifications" in result.stdout
    assert "config.yml" in result.stdout


def test_fails_on_unwritable_tracked_dir(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    sub = repo / "observability"
    sub.mkdir()
    (sub / "dashboard.json").write_text("{}\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

    # Simulate a root-owned directory: current user can read/exec but not write.
    os.chmod(sub, stat.S_IRUSR | stat.S_IXUSR)
    try:
        result = _run(repo)
        assert result.returncode == 1, result.stdout
        assert "observability" in result.stdout
        assert "sudo chown -R" in result.stdout
        # Never runs sudo itself: ownership must be unchanged.
        assert os.stat(sub).st_uid == os.getuid()
    finally:
        os.chmod(sub, stat.S_IRWXU)


def test_fails_on_unwritable_tracked_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    f = repo / "tailscale-state.json"
    f.write_text("{}\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

    os.chmod(f, stat.S_IRUSR)
    try:
        result = _run(repo)
        assert result.returncode == 1, result.stdout
        assert "tailscale-state.json" in result.stdout
        assert "sudo chown -R" in result.stdout
    finally:
        os.chmod(f, stat.S_IRUSR | stat.S_IWUSR)
