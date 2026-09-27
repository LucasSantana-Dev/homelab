"""Tests for scripts/deployment/deployed-sha.sh.

Tracks the SHA actually deployed by the last successful `make deploy` so
apply-config-changes.sh can diff against it. State dir mirrors the
ADR-0023 root-owned-directory fallback already used by
record-deploy-health.sh: writes are best-effort, never fatal.
"""

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "deployment" / "deployed-sha.sh"


def _run(args, state_dir: Path) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "HOMELAB_STATE_DIR": str(state_dir),
        "HOMELAB_DEPLOYED_SHA_FILE": str(state_dir / "deployed-sha"),
    }
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env
    )


def test_read_returns_empty_when_no_state_file(tmp_path):
    state_dir = tmp_path / "state"
    result = _run(["read"], state_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_write_then_read_roundtrip(tmp_path):
    state_dir = tmp_path / "state"
    write_result = _run(["write", "abc123def"], state_dir)
    assert write_result.returncode == 0, write_result.stdout + write_result.stderr

    read_result = _run(["read"], state_dir)
    assert read_result.returncode == 0
    assert read_result.stdout.strip() == "abc123def"


def test_write_creates_state_dir_if_missing(tmp_path):
    state_dir = tmp_path / "does" / "not" / "exist"
    write_result = _run(["write", "deadbeef"], state_dir)
    assert write_result.returncode == 0, write_result.stdout + write_result.stderr
    assert (state_dir / "deployed-sha").read_text().strip() == "deadbeef"


def test_write_falls_back_gracefully_when_unwritable(tmp_path):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    os.chmod(state_dir, 0o555)
    try:
        # No sudo available in the test PATH override below -> should not
        # raise, should not crash, and should exit 0 (best-effort per
        # record-deploy-health.sh's pattern).
        env = {
            **os.environ,
            "HOMELAB_STATE_DIR": str(state_dir),
            "HOMELAB_DEPLOYED_SHA_FILE": str(state_dir / "deployed-sha"),
            "PATH": "/usr/bin:/bin",  # no writable sudo shim on this PATH
        }
        result = subprocess.run(
            ["bash", str(SCRIPT), "write", "abc123"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert not (state_dir / "deployed-sha").exists()
    finally:
        os.chmod(state_dir, 0o755)


def test_unknown_subcommand_errors(tmp_path):
    state_dir = tmp_path / "state"
    result = _run(["bogus"], state_dir)
    assert result.returncode == 1
    assert "usage" in result.stderr
