"""Tests for scripts/monitoring/compose-services-exporter.sh.

`docker` is stubbed on PATH: a fake binary answers `compose config
--services`, `compose ps --status running --format '{{.Name}}'`, and
`inspect --format '...'` from small data files, so the script runs against a
scripted fleet of containers without a real Docker daemon.
"""

import os
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "monitoring" / "compose-services-exporter.sh"

FAKE_DOCKER = """#!/bin/bash
# $FAKE_DOCKER_DATA holds:
#   expected_services.txt   one service name per line
#   running_names.txt       one running container name per line
#   container_info.txt       "name|oneoff|service" per line, looked up by `inspect`
if [ "$1" = "compose" ] && [ "$2" = "config" ]; then
  cat "$FAKE_DOCKER_DATA/expected_services.txt"
  exit 0
fi
if [ "$1" = "compose" ] && [ "$2" = "ps" ]; then
  cat "$FAKE_DOCKER_DATA/running_names.txt"
  exit 0
fi
if [ "$1" = "inspect" ]; then
  name="${@: -1}"
  line=$(grep -F "$name|" "$FAKE_DOCKER_DATA/container_info.txt")
  [ -n "$line" ] || exit 1
  printf '%s\\n' "${line#*|}"
  exit 0
fi
exit 1
"""


def _install_fake_docker(bin_dir: Path) -> None:
    bin_dir.mkdir(exist_ok=True)
    docker = bin_dir / "docker"
    docker.write_text(FAKE_DOCKER)
    docker.chmod(docker.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _run(tmp_path, expected_services, running_names, container_info):
    tmp_path.mkdir(parents=True, exist_ok=True)
    bin_dir = tmp_path / "fakebin"
    _install_fake_docker(bin_dir)

    data_dir = tmp_path / "fakedata"
    data_dir.mkdir()
    (data_dir / "expected_services.txt").write_text("\n".join(expected_services) + "\n")
    (data_dir / "running_names.txt").write_text("\n".join(running_names) + "\n")
    (data_dir / "container_info.txt").write_text(
        "\n".join(f"{n}|{o}|{s}" for n, o, s in container_info) + "\n"
    )

    textfile_dir = tmp_path / "textfile"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "FAKE_DOCKER_DATA": str(data_dir),
        "REPO_DIR": str(repo_dir),
        "TEXTFILE_DIR": str(textfile_dir),
    }
    result = subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True
    )
    metrics = (textfile_dir / "homelab-compose-services.prom").read_text()
    return result, metrics


def test_leftover_oneoff_container_does_not_mask_a_down_service(tmp_path):
    """svcA's only "running" container is a leftover `docker compose run`
    one-off: the service itself has no real long-lived container and must
    be reported as down, not as running."""
    result, metrics = _run(
        tmp_path,
        expected_services=["svcA", "svcB", "svcC"],
        running_names=["svcA_run_1", "svcB_1"],
        container_info=[
            ("svcA_run_1", "True", "svcA"),
            ("svcB_1", "False", "svcB"),
        ],
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'homelab_compose_service_running{service="svcA"} 0' in metrics
    assert 'homelab_compose_service_running{service="svcB"} 1' in metrics
    assert 'homelab_compose_service_running{service="svcC"} 0' in metrics
    assert "homelab_compose_services_not_running 2" in metrics


def test_service_name_with_regex_metachar_matched_literally(tmp_path):
    """`grep -qx` (no -F) would treat a service name's `.` as "any
    character" and could match a container it does not actually name."""
    result, metrics = _run(
        tmp_path / "decoy",
        expected_services=["web.beta"],
        # "webXbeta" would satisfy the regex `web.beta` (the dot matches any
        # char) but must NOT satisfy a literal, fixed-string match.
        running_names=["webXbeta"],
        container_info=[("webXbeta", "False", "webXbeta")],
    )
    assert 'homelab_compose_service_running{service="web.beta"} 0' in metrics

    result2, metrics2 = _run(
        tmp_path / "real",
        expected_services=["web.beta"],
        running_names=["c1"],
        container_info=[("c1", "False", "web.beta")],
    )
    assert 'homelab_compose_service_running{service="web.beta"} 1' in metrics2
