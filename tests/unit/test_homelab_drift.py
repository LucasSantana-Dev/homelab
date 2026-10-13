"""Tests for the agent-box side of scripts/agent-tasks/homelab-drift.sh.

The script needs the host (log dir, SOPS, ssh), so these tests run only the command
it sends over ssh, with a throwaway origin and checkout.
"""

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "agent-tasks" / "homelab-drift.sh"
START = 'RESULT=$(ssh agent-box bash -c "'
END = '" 2>/dev/null) || RESULT='


def _remote_command(origin, checkout):
    text = SCRIPT.read_text()
    body = text[text.index(START) + len(START) : text.index(END)]
    body = body.replace("$PROMPT", "drift-prompt")
    body = body.replace("https://github.com/LucasSantana-Dev/homelab.git", str(origin))
    return body.replace("/workspace/.drift-homelab", str(checkout))


def _git(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _commit(repo, msg):
    _git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        msg,
    )


def _origin(tmp_path, with_release=True):
    origin = tmp_path / "origin"
    _git(tmp_path, "init", "-q", "-b", "main", str(origin))
    _commit(origin, "base")
    if with_release:
        _git(origin, "branch", "release")
    _commit(origin, "main only")
    return origin


def _run(tmp_path, origin):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "claude"
    # Reports which commit the review would read.
    stub.write_text("#!/bin/sh\necho NO_DRIFT $(git rev-parse HEAD)\n")
    stub.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    checkout = tmp_path / "checkout"
    cmd = _remote_command(origin, checkout)
    res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, env=env)
    return res, checkout


def test_drift_never_touches_the_shared_workspace():
    assert "/workspace/homelab" not in SCRIPT.read_text()


def test_drift_reads_release_not_main(tmp_path):
    origin = _origin(tmp_path)
    res, _ = _run(tmp_path, origin)
    assert res.returncode == 0, res.stderr
    assert res.stdout.split() == ["NO_DRIFT", _git(origin, "rev-parse", "release")]


def test_next_run_follows_release_and_drops_local_edits(tmp_path):
    origin = _origin(tmp_path)
    _, checkout = _run(tmp_path, origin)
    _git(origin, "branch", "-f", "release", "main")
    (checkout / "stray").write_text("x")
    _git(checkout, "add", "stray")
    res, _ = _run(tmp_path, origin)
    assert res.returncode == 0, res.stderr
    assert res.stdout.split() == ["NO_DRIFT", _git(origin, "rev-parse", "release")]
    assert not (checkout / "stray").exists()


def test_failed_refresh_does_not_run_claude(tmp_path):
    # No release branch on origin: the fetch fails, and claude must not read a
    # stale or empty checkout.
    origin = _origin(tmp_path, with_release=False)
    res, _ = _run(tmp_path, origin)
    assert res.returncode != 0
    assert "NO_DRIFT" not in res.stdout
