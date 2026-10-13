"""Tests for the agent-box side of scripts/agent-tasks/hermes-pr-review.sh.

The script needs the self-hosted runner (log dir, gh, ssh), so these tests run only
the command it sends over ssh, against a throwaway repo in place of
/workspace/homelab.
"""

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "agent-tasks" / "hermes-pr-review.sh"


def _remote_command(workspace, pr=7, base="release"):
    """The ssh command string as agent-box receives it after local expansion."""
    lines = SCRIPT.read_text().splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == "agent@localhost \\")
    end = next(i for i in range(start, len(lines)) if '" 2>&1); then' in lines[i])
    body = "\n".join(lines[start + 1 : end + 1])
    body = body[body.index('"') + 1 : body.rindex('" 2>&1); then')]
    body = body.replace("$PR_NUMBER", str(pr)).replace("$BASE_REF", base)
    body = body.replace("\\$", "$").replace('\\"', '"')
    return body.replace("/workspace/homelab", str(workspace))


def _git(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _commit(repo, msg):
    ident = ["-c", "user.name=t", "-c", "user.email=t@t"]
    _git(repo, *ident, "commit", "-q", "--allow-empty", "-m", msg)


def _workspace(tmp_path, with_pr=True):
    origin = tmp_path / "origin"
    _git(tmp_path, "init", "-q", "-b", "main", str(origin))
    _commit(origin, "base")
    if with_pr:
        _commit(origin, "pr")
        _git(origin, "update-ref", "refs/pull/7/head", "HEAD")
        _git(origin, "reset", "-q", "--hard", "HEAD~1")
    ws = tmp_path / "ws"
    _git(tmp_path, "clone", "-q", str(origin), str(ws))
    return ws


def _run(tmp_path, ws, claude="echo review-text"):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "claude"
    stub.write_text(f"#!/bin/sh\n{claude}\n")
    stub.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    return subprocess.run(
        ["bash", "-c", _remote_command(ws)], capture_output=True, text=True, env=env
    )


def test_review_prints_output_and_restores_main(tmp_path):
    ws = _workspace(tmp_path)
    res = _run(tmp_path, ws)
    assert res.returncode == 0, res.stderr
    assert res.stdout == "review-text"
    assert _git(ws, "symbolic-ref", "--short", "HEAD") == "main"
    assert _git(ws, "branch", "--list", "hermes-pr-7") == ""


def test_failed_review_still_restores_main(tmp_path):
    ws = _workspace(tmp_path)
    res = _run(tmp_path, ws, claude="echo boom; exit 3")
    assert res.returncode == 3
    assert _git(ws, "symbolic-ref", "--short", "HEAD") == "main"


def test_failed_fetch_restores_main(tmp_path):
    # No refs/pull/7/head on origin: the fetch fails and set -e exits early.
    ws = _workspace(tmp_path, with_pr=False)
    res = _run(tmp_path, ws)
    assert res.returncode != 0
    assert _git(ws, "symbolic-ref", "--short", "HEAD") == "main"
    assert _git(ws, "branch", "--list", "hermes-pr-7") == ""


def test_review_fails_when_main_cannot_be_restored(tmp_path):
    # The PR changes a tracked file and the review edits it: checkout main refuses
    # to overwrite the edit, so the run must fail, not report success.
    ws = _workspace(tmp_path, with_pr=False)
    origin = tmp_path / "origin"
    (origin / "f").write_text("base\n")
    _git(origin, "add", "f")
    _commit(origin, "add f")
    (origin / "f").write_text("pr\n")
    _git(origin, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "pr")
    _git(origin, "update-ref", "refs/pull/7/head", "HEAD")
    _git(origin, "reset", "-q", "--hard", "HEAD~1")
    _git(ws, "pull", "-q")
    res = _run(tmp_path, ws, claude=f"echo edited > {ws / 'f'}; echo review-text")
    assert res.returncode != 0
    assert "could not restore main" in res.stdout
