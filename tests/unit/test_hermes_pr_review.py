"""Tests for the agent-box side of scripts/agent-tasks/hermes-pr-review.sh.

The script needs the self-hosted runner (log dir, gh, ssh), so these tests run only
the command it sends over ssh, with a throwaway origin and review checkout.
"""

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "agent-tasks" / "hermes-pr-review.sh"


def _remote_command(origin, review_dir, pr=7, base="release"):
    """The ssh command string as agent-box receives it after local expansion."""
    lines = SCRIPT.read_text().splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == "agent@localhost \\")
    end = next(i for i in range(start, len(lines)) if '" 2>&1); then' in lines[i])
    body = "\n".join(lines[start + 1 : end + 1])
    body = body[body.index('"') + 1 : body.rindex('" 2>&1); then')]
    body = body.replace("$PR_NUMBER", str(pr)).replace("$BASE_REF", base)
    body = body.replace("$REPO", "o/r")
    body = body.replace("\\$", "$").replace('\\"', '"')
    body = body.replace("https://github.com/o/r.git", str(origin))
    return body.replace("/workspace/.hermes-review", str(review_dir))


def _git(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _commit(repo, msg):
    ident = ["-c", "user.name=t", "-c", "user.email=t@t"]
    _git(repo, *ident, "commit", "-q", "--allow-empty", "-m", msg)


def _origin(tmp_path, with_pr=True):
    origin = tmp_path / "origin"
    _git(tmp_path, "init", "-q", "-b", "main", str(origin))
    _commit(origin, "base")
    _git(origin, "branch", "release")
    if with_pr:
        _commit(origin, "pr")
        _git(origin, "update-ref", "refs/pull/7/head", "HEAD")
        _git(origin, "reset", "-q", "--hard", "HEAD~1")
    return origin


def _run(tmp_path, origin, claude="echo review-text", cmd_edit=None):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "claude"
    stub.write_text(f"#!/bin/sh\n{claude}\n")
    stub.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    review = tmp_path / "review"
    cmd = _remote_command(origin, review)
    if cmd_edit:
        cmd = cmd_edit(cmd)
    res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, env=env)
    return res, review


needs_flock = pytest.mark.skipif(
    shutil.which("flock") is None, reason="flock (util-linux) not installed"
)


def test_review_never_touches_the_shared_workspace():
    assert "/workspace/homelab" not in _remote_command("o", "r")


@needs_flock
def test_review_clones_its_own_checkout_and_cleans_up(tmp_path):
    origin = _origin(tmp_path)
    res, review = _run(tmp_path, origin)
    assert res.returncode == 0, res.stderr
    assert res.stdout == "review-text"
    assert _git(review, "branch", "--list", "hermes-pr-7") == ""
    # The base the prompt names is there to diff against.
    base = _git(origin, "rev-parse", "release")
    assert _git(review, "rev-parse", "origin/release") == base


@needs_flock
def test_second_review_reuses_the_checkout_and_refreshes_base(tmp_path):
    origin = _origin(tmp_path)
    _run(tmp_path, origin)
    _commit(origin, "base moves")
    _git(origin, "branch", "-f", "release", "HEAD")
    res, review = _run(tmp_path, origin)
    assert res.returncode == 0, res.stderr
    base = _git(origin, "rev-parse", "release")
    assert _git(review, "rev-parse", "origin/release") == base


@needs_flock
def test_failed_review_still_cleans_up(tmp_path):
    origin = _origin(tmp_path)
    res, review = _run(tmp_path, origin, claude="echo boom; exit 3")
    assert res.returncode == 3
    assert _git(review, "branch", "--list", "hermes-pr-7") == ""


@needs_flock
def test_failed_fetch_cleans_up(tmp_path):
    # No refs/pull/7/head on origin: the fetch fails and set -e exits early.
    origin = _origin(tmp_path, with_pr=False)
    res, review = _run(tmp_path, origin)
    assert res.returncode != 0
    assert _git(review, "branch", "--list", "hermes-pr-7") == ""


def _short_wait(cmd):
    # flock -w 60 is shortened so the tests stay fast.
    return cmd.replace("-w 60 8", "-w 2 8")


def _hold_lock(tmp_path, pr):
    """A review of `pr` still running on agent-box: holds the lock, owns the file."""
    lock, owner = tmp_path / "review.lock", tmp_path / "review.owner"
    holder = subprocess.Popen(
        ["bash", "-c", f'exec 8>{lock}; flock 8; echo "{pr} $$" >{owner}; sleep 30'],
        start_new_session=True,
    )
    for _ in range(100):
        if owner.exists() and owner.read_text().strip():
            return holder
        time.sleep(0.05)
    holder.kill()
    raise AssertionError("holder never took the lock")


def _stop(holder):
    try:
        os.killpg(holder.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    holder.wait()


@needs_flock
def test_review_waits_for_another_prs_review(tmp_path):
    origin = _origin(tmp_path)
    holder = _hold_lock(tmp_path, pr=8)
    try:
        res, _ = _run(tmp_path, origin, cmd_edit=_short_wait)
        assert holder.poll() is None, "another PR's review must not be stopped"
    finally:
        _stop(holder)
    assert res.returncode == 75
    assert "another review holds the checkout" in res.stdout


@needs_flock
def test_review_stops_a_cancelled_run_of_the_same_pr(tmp_path):
    # cancel-in-progress kills the job, not the review on agent-box; the old
    # run's result is stale, so the new run takes over instead of giving up.
    origin = _origin(tmp_path)
    holder = _hold_lock(tmp_path, pr=7)
    try:
        res, _ = _run(tmp_path, origin, cmd_edit=_short_wait)
        assert holder.wait(timeout=5) == -signal.SIGTERM
    finally:
        _stop(holder)
    assert res.returncode == 0, res.stdout + res.stderr
    assert res.stdout == "review-text"
    assert not (tmp_path / "review.owner").exists()


@needs_flock
def test_a_child_left_running_does_not_hold_the_lock(tmp_path):
    origin = _origin(tmp_path)
    pid_file = tmp_path / "bg.pid"
    claude = f"sleep 30 >/dev/null 2>&1 & echo $! >{pid_file}; echo review-text"
    try:
        _run(tmp_path, origin, claude=claude)
        res, _ = _run(tmp_path, origin, cmd_edit=_short_wait)
    finally:
        if pid_file.exists():
            os.kill(int(pid_file.read_text()), signal.SIGKILL)
    assert res.returncode == 0, res.stdout + res.stderr


@needs_flock
def test_stale_git_lock_from_a_killed_run_is_cleared(tmp_path):
    origin = _origin(tmp_path)
    _, review = _run(tmp_path, origin)
    (review / ".git" / "index.lock").touch()
    res, _ = _run(tmp_path, origin)
    assert res.returncode == 0, res.stdout + res.stderr
    assert not (review / ".git" / "index.lock").exists()


def _resolve_base(tmp_path, gh_out, base_arg="main"):
    """Run the script's PR head and base lookup against a gh stub."""
    text = SCRIPT.read_text()
    tail = '    BASE_REF="$PR_BASE"\nfi\n'
    start = text.index("PR_INFO=$(")
    end = text.index(tail) + len(tail)
    bin_dir = tmp_path / "ghbin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(f"#!/bin/sh\necho '{gh_out}'\n")
    (bin_dir / "gh").chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    prog = (
        f"log() {{ :; }}; PR_NUMBER=7 REPO=o/r BASE_REF={base_arg}\n"
        + text[start:end]
        + 'echo "$HEAD_SHA $BASE_REF"\n'
    )
    res = subprocess.run(["bash", "-c", prog], capture_output=True, text=True, env=env)
    assert res.returncode == 0, res.stderr
    return res.stdout.strip()


def test_review_diffs_against_the_prs_own_base(tmp_path):
    # A manual run passes the workflow default 'main'; the PR targets release.
    assert _resolve_base(tmp_path, "abc123 release") == "abc123 release"


def test_unsafe_pr_base_keeps_the_given_one(tmp_path):
    assert _resolve_base(tmp_path, "abc123 a..b") == "abc123 main"
