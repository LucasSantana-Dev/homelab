"""Tests for scripts/deployment/deployed-sha.sh.

Tracks the SHA actually deployed by the last successful `make deploy` so
apply-config-changes.sh can diff against it. State dir mirrors the
ADR-0023 root-owned-directory fallback already used by
record-deploy-health.sh, with a passwordless-sudo fallback for both the
directory (fresh host, `/var/lib/homelab` doesn't exist yet) and the file.

These tests never rely on the test host's real `sudo` (CI runners commonly
ship passwordless sudo for the CI user, which would make a "no sudo
available" premise false and defeat the simulation) -- they put a fake
`sudo` first on PATH instead, so behavior is hermetic regardless of the
host's actual sudo configuration.
"""

import os
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "deployment" / "deployed-sha.sh"

FAKE_SUDO_DENY = """#!/bin/bash
# Simulates no passwordless sudo configured: always refuses.
echo "$@" >> "$FAKE_SUDO_LOG"
exit 1
"""


def _fake_sudo_bin(tmp_path: Path, script: str) -> Path:
    bindir = tmp_path / "sudo-bin"
    bindir.mkdir(exist_ok=True)
    sudo = bindir / "sudo"
    sudo.write_text(script)
    sudo.chmod(sudo.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bindir


def _run(
    args, state_dir: Path, extra_env: dict | None = None
) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "HOMELAB_STATE_DIR": str(state_dir),
        "HOMELAB_DEPLOYED_SHA_FILE": str(state_dir / "deployed-sha"),
    }
    if extra_env:
        env.update(extra_env)
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


def test_write_warns_loudly_when_dir_unwritable_and_sudo_denied(tmp_path):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    os.chmod(state_dir, 0o555)
    sudo_bindir = _fake_sudo_bin(tmp_path, FAKE_SUDO_DENY)
    sudo_log = tmp_path / "sudo.log"
    sudo_log.write_text("")
    try:
        result = _run(
            ["write", "abc123"],
            state_dir,
            extra_env={
                "PATH": f"{sudo_bindir}:{os.environ['PATH']}",
                "FAKE_SUDO_LOG": str(sudo_log),
            },
        )
        # Genuinely stuck (unwritable dir, no working sudo): this is now a
        # loud, non-zero-exit failure, not a silent no-op. The Makefile is
        # responsible for making the overall `make deploy` step non-fatal.
        assert result.returncode == 1, result.stdout + result.stderr
        assert "could not persist" in result.stderr
        assert not (state_dir / "deployed-sha").exists()
        # It did try the sudo fallback (not just give up on the -w check).
        assert "tee" in sudo_log.read_text()
    finally:
        os.chmod(state_dir, 0o755)


def test_write_attempts_sudo_mkdir_when_parent_missing_and_direct_mkdir_fails(tmp_path):
    """Fresh host: /var/lib/homelab doesn't exist yet and its parent is
    root-owned, so plain `mkdir -p` can't create it. The script must at
    least attempt `sudo -n mkdir -p` before giving up."""
    parent = tmp_path / "var-lib"
    parent.mkdir()
    state_dir = parent / "homelab"  # does not exist
    os.chmod(parent, 0o555)  # not writable -> mkdir -p state_dir fails directly
    sudo_bindir = _fake_sudo_bin(tmp_path, FAKE_SUDO_DENY)
    sudo_log = tmp_path / "sudo.log"
    sudo_log.write_text("")
    try:
        result = _run(
            ["write", "abc123"],
            state_dir,
            extra_env={
                "PATH": f"{sudo_bindir}:{os.environ['PATH']}",
                "FAKE_SUDO_LOG": str(sudo_log),
            },
        )
        assert result.returncode == 1, result.stdout + result.stderr
        assert "could not persist" in result.stderr
        log_text = sudo_log.read_text()
        assert "mkdir -p" in log_text
        assert str(state_dir) in log_text
    finally:
        os.chmod(parent, 0o755)


def test_unknown_subcommand_errors(tmp_path):
    state_dir = tmp_path / "state"
    result = _run(["bogus"], state_dir)
    assert result.returncode == 1
    assert "usage" in result.stderr
