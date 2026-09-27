"""Tests for scripts/check_deploy_drift.sh (#269).

`ssh` is stubbed on PATH: the fake binary runs the given remote command
string with a local `bash -c`, so REMOTE_DIR can just be a real local
directory standing in for "the host". This never touches the network or a
real host, and it doubles as a faithful injection probe: if the script ever
builds an unescaped remote command, the fake ssh executes it exactly as a
real remote shell would.
"""

import os
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_deploy_drift.sh"

FAKE_SSH = """#!/bin/bash
# Runs the remote command locally against REMOTE_DIR (a real local dir in
# tests) instead of over a real SSH connection.
last="${@: -1}"
if [ -n "${FAKE_SSH_BREAK_SUBSTRING:-}" ] && [[ "$last" == *"$FAKE_SSH_BREAK_SUBSTRING"* ]]; then
  exit "${FAKE_SSH_BREAK_RC:-255}"
fi
exec bash -c "$last"
"""


def _install_fake_ssh(bin_dir: Path) -> None:
    bin_dir.mkdir(exist_ok=True)
    ssh = bin_dir / "ssh"
    ssh.write_text(FAKE_SSH)
    ssh.chmod(ssh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _run(repo_dir: Path, remote_dir, bin_dir_extra=None, extra_env=None):
    bin_dir = repo_dir / ".fakebin"
    _install_fake_ssh(bin_dir)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT), "fakehost", str(remote_dir)],
        cwd=repo_dir,
        env=env,
        capture_output=True,
        text=True,
    )


def _compose(repo_dir: Path, name: str, body: str) -> None:
    d = repo_dir / "compose"
    d.mkdir(exist_ok=True)
    (d / name).write_text(body)


def test_apostrophe_in_remote_dir_cannot_inject_a_command(tmp_path):
    """The old code built `test -f '$REMOTE_DIR/$f'` by hand: an apostrophe in
    REMOTE_DIR closed the quote early and let a `;`-separated command run on
    "the host". printf %q must make that a single, inert argument instead."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _compose(repo_dir, "svc.yml", "services:\n  a:\n    image: nginx\n")

    marker = tmp_path / "pwned"
    malicious_remote_dir = f"/nonexistent'; touch {marker} ; echo '"

    result = _run(repo_dir, malicious_remote_dir)

    assert not marker.exists(), (
        "command injection via REMOTE_DIR executed a second command: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_host_only_block_scalar_secret_is_withheld_from_the_diff(tmp_path):
    """A block-scalar secret that exists ONLY on the host side (never in the
    repo file) must not slip past `diff_is_safe_to_print` just because the
    repo-side file has no block scalar to trigger on."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _compose(
        repo_dir, "svc.yml", "services:\n  a:\n    environment:\n      TOKEN: set\n"
    )

    remote_dir = tmp_path / "remote"
    (remote_dir / "compose").mkdir(parents=True)
    (remote_dir / "compose" / "svc.yml").write_text(
        "services:\n  a:\n    environment:\n      TOKEN: |\n        supersecret123\n"
    )

    result = _run(repo_dir, remote_dir)

    assert "supersecret123" not in result.stdout
    assert "body withheld" in result.stdout
    assert result.returncode == 1


def test_ssh_failure_on_existence_check_is_distinct_from_absent(tmp_path):
    """A `test -f` that fails to even run (dropped connection, exit 255) must
    not be reported as ABSENT: that misreports "we don't know" as drift."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _compose(repo_dir, "flaky.yml", "services:\n  a:\n    image: nginx\n")

    remote_dir = tmp_path / "remote"
    remote_dir.mkdir()

    result = _run(
        repo_dir,
        remote_dir,
        extra_env={
            "FAKE_SSH_BREAK_SUBSTRING": "compose/flaky.yml",
            "FAKE_SSH_BREAK_RC": "255",
        },
    )

    assert "ABSENT compose/flaky.yml" not in result.stdout
    assert "ERROR compose/flaky.yml" in result.stdout
    assert result.returncode == 2


def test_absent_file_still_reported_when_ssh_succeeds(tmp_path):
    """Control for the previous test: a real "file not there" (test -f exits
    1, ssh itself succeeds) must still be reported as ABSENT."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _compose(repo_dir, "svc.yml", "services:\n  a:\n    image: nginx\n")

    remote_dir = tmp_path / "remote"
    remote_dir.mkdir()

    result = _run(repo_dir, remote_dir)

    assert "ABSENT compose/svc.yml" in result.stdout
    assert result.returncode == 1


def test_unreadable_manifest_does_not_abort_discovery_of_other_files(tmp_path):
    """One manifest that cannot be decoded as UTF-8 must be skipped, not
    crash `list_deployable_files` and silently drop every other file too."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _compose(repo_dir, "good.yml", "services:\n  a:\n    image: nginx\n")
    (repo_dir / "compose" / "bad.yml").write_bytes(b"\xff\xfe\x00bad-utf8")

    remote_dir = tmp_path / "remote"
    remote_dir.mkdir()

    result = _run(repo_dir, remote_dir)

    assert "Traceback" not in result.stderr
    assert "ABSENT compose/good.yml" in result.stdout
    assert "ABSENT compose/bad.yml" in result.stdout
