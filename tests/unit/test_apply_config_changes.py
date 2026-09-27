"""Tests for scripts/deployment/apply-config-changes.sh.

Three manual deploys on 2026-09-27 hit config that neither `git pull` nor
`docker compose up -d` gets a running container to actually use:
  - config/caddy/Caddyfile is bind-mounted as a FILE; git swaps the inode but
    caddy-lan keeps serving the old one until restarted.
  - config/prometheus/ and config/alertmanager/ are directory mounts; the new
    files land inside the container but neither process re-reads them
    without a signal.

These tests run the script against a real temporary git repo with a fake
`docker` executable first on PATH that logs its argv, so we can assert which
container actions did (and did not) happen for a given diff.
"""

import os
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "deployment" / "apply-config-changes.sh"

FAKE_DOCKER = """#!/bin/bash
# Fake docker for tests: logs every invocation, simulates exec/logs/restart/
# kill/inspect. `kill` touches a per-container marker file so `logs` only
# returns FAKE_DOCKER_LOGS_OUTPUT for calls made *after* that container was
# signaled -- mirrors real "only new log lines count" semantics without
# depending on wall-clock precision.
echo "$@" >> "$FAKE_DOCKER_LOG"
args=("$@")
last="${args[$((${#args[@]} - 1))]}"
case "$1" in
    exec)
        case "$3" in
            cat)
                if [[ -n "${FAKE_DOCKER_EXEC_OUTPUT:-}" ]]; then
                    cat "$FAKE_DOCKER_EXEC_OUTPUT"
                fi
                exit 0
                ;;
            caddy)
                [[ "${FAKE_DOCKER_VALIDATE_FAIL:-0}" == "1" ]] && exit 1
                exit 0
                ;;
            wget)
                [[ "${FAKE_DOCKER_ADMIN_API_FAIL:-0}" == "1" ]] && exit 1
                exit 0
                ;;
            *)
                exit 0
                ;;
        esac
        ;;
    logs)
        marker_dir="${FAKE_DOCKER_KILL_MARKER_DIR:-/nonexistent}"
        if [[ -n "${FAKE_DOCKER_LOGS_OUTPUT:-}" && -f "${marker_dir}/${last}.killed" ]]; then
            printf '%s\\n' "$FAKE_DOCKER_LOGS_OUTPUT"
        fi
        exit 0
        ;;
    restart)
        [[ "${FAKE_DOCKER_RESTART_FAIL:-0}" == "1" ]] && exit 1
        exit 0
        ;;
    kill)
        [[ "${FAKE_DOCKER_KILL_FAIL:-0}" == "1" ]] && exit 1
        if [[ -n "${FAKE_DOCKER_KILL_MARKER_DIR:-}" ]]; then
            mkdir -p "$FAKE_DOCKER_KILL_MARKER_DIR"
            touch "${FAKE_DOCKER_KILL_MARKER_DIR}/${last}.killed"
        fi
        exit 0
        ;;
    inspect)
        fmt="$3"
        case "$fmt" in
            *State.Running*)
                echo "${FAKE_DOCKER_RUNNING:-true}"
                ;;
            *RestartCount*)
                if [[ "${FAKE_DOCKER_CRASH_LOOP:-0}" == "1" ]]; then
                    counter_file="${FAKE_DOCKER_RESTART_COUNTER_FILE:-/tmp/fake-docker-restart-counter}"
                    count=0
                    [[ -f "$counter_file" ]] && count="$(cat "$counter_file")"
                    count=$((count + 1))
                    echo "$count" > "$counter_file"
                    echo "$count"
                else
                    echo "0"
                fi
                ;;
            *)
                echo ""
                ;;
        esac
        exit 0
        ;;
    *)
        exit 0
        ;;
esac
"""


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)


def _commit(repo: Path, msg: str) -> str:
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=repo, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _fake_docker_bin(tmp_path: Path) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    docker = bindir / "docker"
    docker.write_text(FAKE_DOCKER)
    docker.chmod(docker.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bindir


def _run(
    repo: Path, old_sha: str, bindir: Path, log: Path, extra_env: dict | None = None
):
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "FAKE_DOCKER_LOG": str(log),
        "FAKE_DOCKER_KILL_MARKER_DIR": str(log.parent / "kill-markers"),
        "FAKE_DOCKER_RESTART_COUNTER_FILE": str(log.parent / "restart-counter"),
        "RELOAD_POLL_ATTEMPTS": "2",
        "RELOAD_POLL_INTERVAL": "0",
    }
    if extra_env:
        env.update(extra_env)
    args = ["bash", str(SCRIPT)]
    if old_sha is not None:
        args.append(old_sha)
    return subprocess.run(args, cwd=repo, env=env, capture_output=True, text=True)


def _setup_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "config" / "caddy").mkdir(parents=True)
    (repo / "config" / "prometheus").mkdir(parents=True)
    (repo / "config" / "alertmanager").mkdir(parents=True)
    (repo / "config" / "caddy" / "Caddyfile").write_text(
        'example.home {\n  respond "v1"\n}\n'
    )
    (repo / "config" / "prometheus" / "rules.yml").write_text("groups: []\n")
    (repo / "config" / "alertmanager" / "alertmanager.yml").write_text("route: {}\n")
    (repo / "unrelated.txt").write_text("hi\n")
    return repo


def test_nothing_changed_skips_all_docker_calls(tmp_path):
    repo = _setup_repo(tmp_path)
    old_sha = _commit(repo, "init")
    (repo / "unrelated.txt").write_text("bye\n")
    _commit(repo, "unrelated change")

    bindir = _fake_docker_bin(tmp_path)
    log = tmp_path / "docker.log"
    log.write_text("")

    result = _run(repo, old_sha, bindir, log)
    assert result.returncode == 0, result.stdout + result.stderr
    assert log.read_text().strip() == ""


def test_caddyfile_change_restarts_and_verifies_caddy_lan(tmp_path):
    repo = _setup_repo(tmp_path)
    old_sha = _commit(repo, "init")
    (repo / "config" / "caddy" / "Caddyfile").write_text(
        'example.home {\n  respond "v2"\n}\n'
    )
    _commit(repo, "caddy change")

    bindir = _fake_docker_bin(tmp_path)
    log = tmp_path / "docker.log"
    log.write_text("")

    # Container "serves" exactly the new host file -> sha256 verification passes.
    result = _run(
        repo,
        old_sha,
        bindir,
        log,
        extra_env={
            "FAKE_DOCKER_EXEC_OUTPUT": str(repo / "config" / "caddy" / "Caddyfile")
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    log_text = log.read_text()
    assert "exec caddy-lan caddy validate" in log_text
    assert "restart caddy-lan" in log_text
    assert "exec caddy-lan cat /etc/caddy/Caddyfile" in log_text
    assert "kill -s HUP prometheus" not in log_text
    assert "kill -s HUP alertmanager" not in log_text


def test_caddyfile_change_fails_when_container_still_stale(tmp_path):
    repo = _setup_repo(tmp_path)
    old_sha = _commit(repo, "init")
    (repo / "config" / "caddy" / "Caddyfile").write_text(
        'example.home {\n  respond "v2"\n}\n'
    )
    _commit(repo, "caddy change")

    bindir = _fake_docker_bin(tmp_path)
    log = tmp_path / "docker.log"
    log.write_text("")
    stale = tmp_path / "stale-caddyfile"
    stale.write_text('example.home {\n  respond "v1"\n}\n')

    result = _run(
        repo, old_sha, bindir, log, extra_env={"FAKE_DOCKER_EXEC_OUTPUT": str(stale)}
    )
    assert result.returncode == 1
    assert "not serving the new Caddyfile" in result.stdout + result.stderr


def test_caddy_restart_failure_is_reported(tmp_path):
    repo = _setup_repo(tmp_path)
    old_sha = _commit(repo, "init")
    (repo / "config" / "caddy" / "Caddyfile").write_text("changed\n")
    _commit(repo, "caddy change")

    bindir = _fake_docker_bin(tmp_path)
    log = tmp_path / "docker.log"
    log.write_text("")

    result = _run(
        repo, old_sha, bindir, log, extra_env={"FAKE_DOCKER_RESTART_FAIL": "1"}
    )
    assert result.returncode == 1
    assert "failed to restart caddy-lan" in result.stdout + result.stderr


def test_caddy_invalid_config_refuses_restart(tmp_path):
    """An invalid new Caddyfile must never take the proxy down: validation
    runs against the live bind mount before any restart, and a failure skips
    the restart entirely."""
    repo = _setup_repo(tmp_path)
    old_sha = _commit(repo, "init")
    (repo / "config" / "caddy" / "Caddyfile").write_text("not valid caddyfile {{{\n")
    _commit(repo, "caddy change")

    bindir = _fake_docker_bin(tmp_path)
    log = tmp_path / "docker.log"
    log.write_text("")

    result = _run(
        repo, old_sha, bindir, log, extra_env={"FAKE_DOCKER_VALIDATE_FAIL": "1"}
    )
    assert result.returncode == 1
    assert "fails `caddy validate`" in result.stdout + result.stderr
    log_text = log.read_text()
    assert "exec caddy-lan caddy validate" in log_text
    assert "restart caddy-lan" not in log_text


def test_caddy_crash_loop_after_restart_detected(tmp_path):
    repo = _setup_repo(tmp_path)
    old_sha = _commit(repo, "init")
    (repo / "config" / "caddy" / "Caddyfile").write_text("changed\n")
    _commit(repo, "caddy change")

    bindir = _fake_docker_bin(tmp_path)
    log = tmp_path / "docker.log"
    log.write_text("")

    result = _run(
        repo,
        old_sha,
        bindir,
        log,
        extra_env={
            "FAKE_DOCKER_EXEC_OUTPUT": str(repo / "config" / "caddy" / "Caddyfile"),
            "FAKE_DOCKER_CRASH_LOOP": "1",
        },
    )
    assert result.returncode == 1
    assert "crash-looping" in result.stdout + result.stderr


def test_caddy_not_running_after_restart_detected(tmp_path):
    repo = _setup_repo(tmp_path)
    old_sha = _commit(repo, "init")
    (repo / "config" / "caddy" / "Caddyfile").write_text("changed\n")
    _commit(repo, "caddy change")

    bindir = _fake_docker_bin(tmp_path)
    log = tmp_path / "docker.log"
    log.write_text("")

    result = _run(
        repo,
        old_sha,
        bindir,
        log,
        extra_env={
            "FAKE_DOCKER_EXEC_OUTPUT": str(repo / "config" / "caddy" / "Caddyfile"),
            "FAKE_DOCKER_RUNNING": "false",
        },
    )
    assert result.returncode == 1
    assert "not running after restart" in result.stdout + result.stderr


def test_caddy_admin_api_not_answering_after_restart_detected(tmp_path):
    """A file-hash match only proves the bind mount is current, not that
    caddy itself is serving: also probe the admin API, same as the compose
    healthcheck."""
    repo = _setup_repo(tmp_path)
    old_sha = _commit(repo, "init")
    (repo / "config" / "caddy" / "Caddyfile").write_text("changed\n")
    _commit(repo, "caddy change")

    bindir = _fake_docker_bin(tmp_path)
    log = tmp_path / "docker.log"
    log.write_text("")

    result = _run(
        repo,
        old_sha,
        bindir,
        log,
        extra_env={
            "FAKE_DOCKER_EXEC_OUTPUT": str(repo / "config" / "caddy" / "Caddyfile"),
            "FAKE_DOCKER_ADMIN_API_FAIL": "1",
        },
    )
    assert result.returncode == 1
    assert "admin API is not answering" in result.stdout + result.stderr


def test_uncommitted_caddyfile_change_is_detected(tmp_path):
    """DEPLOY_FORCE=1 lets `make deploy` run with uncommitted tracked-config
    edits still in the worktree. Those never show up in old-sha..HEAD, so the
    worktree itself must also be diffed against HEAD."""
    repo = _setup_repo(tmp_path)
    old_sha = _commit(repo, "init")
    # No commit: simulates a DEPLOY_FORCE=1 host edit still sitting dirty.
    (repo / "config" / "caddy" / "Caddyfile").write_text(
        'example.home {\n  respond "v2"\n}\n'
    )

    bindir = _fake_docker_bin(tmp_path)
    log = tmp_path / "docker.log"
    log.write_text("")

    result = _run(
        repo,
        old_sha,
        bindir,
        log,
        extra_env={
            "FAKE_DOCKER_EXEC_OUTPUT": str(repo / "config" / "caddy" / "Caddyfile")
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "restart caddy-lan" in log.read_text()


def test_prometheus_change_sends_hup_only(tmp_path):
    repo = _setup_repo(tmp_path)
    old_sha = _commit(repo, "init")
    (repo / "config" / "prometheus" / "rules.yml").write_text("groups: [rule]\n")
    _commit(repo, "prometheus change")

    bindir = _fake_docker_bin(tmp_path)
    log = tmp_path / "docker.log"
    log.write_text("")

    result = _run(
        repo,
        old_sha,
        bindir,
        log,
        extra_env={
            "FAKE_DOCKER_LOGS_OUTPUT": "Completed loading of configuration file"
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    log_text = log.read_text()
    assert "kill -s HUP prometheus" in log_text
    assert "restart caddy-lan" not in log_text
    assert "kill -s HUP alertmanager" not in log_text


def test_prometheus_reload_not_confirmed_fails(tmp_path):
    repo = _setup_repo(tmp_path)
    old_sha = _commit(repo, "init")
    (repo / "config" / "prometheus" / "rules.yml").write_text("groups: [rule]\n")
    _commit(repo, "prometheus change")

    bindir = _fake_docker_bin(tmp_path)
    log = tmp_path / "docker.log"
    log.write_text("")

    result = _run(
        repo, old_sha, bindir, log
    )  # no FAKE_DOCKER_LOGS_OUTPUT -> no confirmation
    assert result.returncode == 1
    assert "did not confirm config reload" in result.stdout + result.stderr


def test_prometheus_kill_failure_reported(tmp_path):
    repo = _setup_repo(tmp_path)
    old_sha = _commit(repo, "init")
    (repo / "config" / "prometheus" / "rules.yml").write_text("groups: [rule]\n")
    _commit(repo, "prometheus change")

    bindir = _fake_docker_bin(tmp_path)
    log = tmp_path / "docker.log"
    log.write_text("")

    result = _run(
        repo,
        old_sha,
        bindir,
        log,
        extra_env={
            "FAKE_DOCKER_KILL_FAIL": "1",
            "FAKE_DOCKER_LOGS_OUTPUT": "Completed loading of configuration file",
        },
    )
    assert result.returncode == 1
    assert "failed to send SIGHUP to prometheus" in result.stdout + result.stderr


def test_alertmanager_change_sends_hup_only(tmp_path):
    repo = _setup_repo(tmp_path)
    old_sha = _commit(repo, "init")
    (repo / "config" / "alertmanager" / "alertmanager.yml").write_text(
        "route: {receiver: x}\n"
    )
    _commit(repo, "alertmanager change")

    bindir = _fake_docker_bin(tmp_path)
    log = tmp_path / "docker.log"
    log.write_text("")

    result = _run(
        repo,
        old_sha,
        bindir,
        log,
        extra_env={
            "FAKE_DOCKER_LOGS_OUTPUT": "Completed loading of configuration file"
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    log_text = log.read_text()
    assert "kill -s HUP alertmanager" in log_text
    assert "kill -s HUP prometheus" not in log_text
    assert "restart caddy-lan" not in log_text


def test_unknown_old_sha_treats_everything_as_changed(tmp_path):
    repo = _setup_repo(tmp_path)
    _commit(repo, "init")

    bindir = _fake_docker_bin(tmp_path)
    log = tmp_path / "docker.log"
    log.write_text("")

    result = _run(
        repo,
        "unknown",
        bindir,
        log,
        extra_env={
            "FAKE_DOCKER_EXEC_OUTPUT": str(repo / "config" / "caddy" / "Caddyfile"),
            "FAKE_DOCKER_LOGS_OUTPUT": "Completed loading of configuration file",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    log_text = log.read_text()
    assert "restart caddy-lan" in log_text
    assert "kill -s HUP prometheus" in log_text
    assert "kill -s HUP alertmanager" in log_text


def test_empty_old_sha_treats_everything_as_changed(tmp_path):
    repo = _setup_repo(tmp_path)
    _commit(repo, "init")

    bindir = _fake_docker_bin(tmp_path)
    log = tmp_path / "docker.log"
    log.write_text("")

    result = _run(
        repo,
        None,
        bindir,
        log,
        extra_env={
            "FAKE_DOCKER_EXEC_OUTPUT": str(repo / "config" / "caddy" / "Caddyfile"),
            "FAKE_DOCKER_LOGS_OUTPUT": "Completed loading of configuration file",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    log_text = log.read_text()
    assert "restart caddy-lan" in log_text
    assert "kill -s HUP prometheus" in log_text
    assert "kill -s HUP alertmanager" in log_text
