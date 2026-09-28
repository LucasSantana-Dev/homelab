"""Tests for scripts/deployment/preflight-pull.sh.

On 2026-09-27, `git pull` stopped halfway through a manual deploy: some
tracked dirs (observability/, tailscale/, a few files) were root-owned, git
hit "unable to unlink old ... Permission denied", and HEAD stayed on the old
commit while ~22 files were already overwritten. This script is meant to
catch that class of failure (unwritable tracked directory, or a dirty
tracked file) before `git pull` ever runs.

The chmod-based "unwritable" simulations below only work when the test
process is a real, non-privileged user: root (and anything with
CAP_DAC_OVERRIDE) ignores the write-permission bit entirely, so `-w` in the
script would report "writable" regardless of mode. Skipped in that case
rather than producing a false pass/fail.
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "deployment" / "preflight-pull.sh"

requires_non_root = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="chmod-based unwritable simulation is meaningless as root",
)


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


@requires_non_root
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
        # Owned by the current user in this simulation (chmod, not chown), so
        # the mode-only fix is suggested, not a chown (that path needs a real
        # ownership mismatch, which requires root to simulate and is not
        # exercised here).
        assert "chmod u+w" in result.stdout
        assert "sudo chown" not in result.stdout
        # Never runs sudo itself: ownership must be unchanged.
        assert os.stat(sub).st_uid == os.getuid()
    finally:
        os.chmod(sub, stat.S_IRWXU)


@requires_non_root
def test_fails_on_unwritable_repo_root(tmp_path):
    """A root-owned checkout root (`.`) blocks writing top-level tracked files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "top-level.yml").write_text("a: 1\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

    os.chmod(repo, stat.S_IRUSR | stat.S_IXUSR)
    try:
        result = _run(repo)
        assert result.returncode == 1, result.stdout
        assert "dir: ." in result.stdout
    finally:
        os.chmod(repo, stat.S_IRWXU)


def test_unwritable_file_in_writable_dir_does_not_block_pull(tmp_path):
    """A read-only tracked FILE inside a writable directory is not a real
    blocker: git unlinks and recreates the file, which only needs write on
    the parent directory. Only directory permissions are checked."""
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
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        os.chmod(f, stat.S_IRUSR | stat.S_IWUSR)
