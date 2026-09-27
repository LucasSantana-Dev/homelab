"""Tests for scripts/monitoring/host-security-audit.sh.

Docker and lynis are stubbed on PATH: a fake `docker` records every
invocation to CALL_LOG and returns just enough canned output to drive the
script through a full Trivy scan without touching the real daemon. `lynis`
is left absent (command -v fails), which the script already treats as a
non-fatal 0/0/0 result.
"""

import os
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "monitoring" / "host-security-audit.sh"

FAKE_DOCKER = """#!/bin/bash
# Records every invocation, then answers just enough to drive the script
# through a full scan of two "running containers" without real Docker.
echo "$*" >> "$CALL_LOG"
case "$1" in
  ps)
    echo c1
    echo c2
    ;;
  inspect)
    last="${@: -1}"
    case "$last" in
      c1) echo "sha256:aaa111|repo/a:latest" ;;
      c2) echo "sha256:bbb222|repo/b:latest" ;;
    esac
    ;;
  image)
    exit 0
    ;;
  save)
    out=""
    prev=""
    for a in "$@"; do
      if [ "$prev" = "-o" ]; then out="$a"; fi
      prev="$a"
    done
    : > "$out"
    ;;
  run)
    echo '{"Results": [{"Vulnerabilities": [{"Severity":"HIGH"},{"Severity":"CRITICAL"}]}]}'
    ;;
  pull)
    exit 0
    ;;
  *)
    exit 1
    ;;
esac
"""


def _install_fake_docker(bin_dir: Path) -> None:
    bin_dir.mkdir(exist_ok=True)
    docker = bin_dir / "docker"
    docker.write_text(FAKE_DOCKER)
    docker.chmod(docker.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _run(tmp_path, extra_env=None):
    bin_dir = tmp_path / "fakebin"
    _install_fake_docker(bin_dir)
    textfile_dir = tmp_path / "textfile"
    report_dir = tmp_path / "report"
    scan_tmp = tmp_path / "scantmp"
    scan_tmp.mkdir()
    call_log = tmp_path / "calls.log"
    call_log.write_text("")
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "TEXTFILE_DIR": str(textfile_dir),
        "REPORT_DIR": str(report_dir),
        "SCAN_TMP": str(scan_tmp),
        "CALL_LOG": str(call_log),
    }
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True
    )
    return result, textfile_dir, report_dir, call_log


def test_scans_by_immutable_image_id_not_mutable_tag(tmp_path):
    result, textfile_dir, report_dir, call_log = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr

    calls = call_log.read_text().splitlines()
    save_calls = [c for c in calls if c.startswith("save ")]
    run_calls = [c for c in calls if c.startswith("run ")]

    # docker save/scan must operate on the immutable image ID resolved via
    # `docker inspect`, never on the mutable repo:tag a retag could move.
    assert any("sha256:aaa111" in c for c in save_calls)
    assert any("sha256:bbb222" in c for c in save_calls)
    assert not any("repo/a:latest" in c for c in save_calls + run_calls)
    assert not any("repo/b:latest" in c for c in save_calls + run_calls)

    # `docker ps -q` (running containers), not `docker ps --format
    # '{{.Image}}'` (the old mutable-tag enumeration).
    assert any(c.strip() == "ps -q" for c in calls)
    assert not any(c.startswith("ps --format") for c in calls)

    # The metric label is still the human repo:tag, for readability.
    metrics = (textfile_dir / "host-security-audit.prom").read_text()
    assert 'image="repo/a:latest"' in metrics
    assert 'image="repo/b:latest"' in metrics
    assert 'host_image_scan_ok{image="repo/a:latest"} 1' in metrics


def test_summary_write_failure_dies_instead_of_continuing_silently(tmp_path):
    """No errexit in this script: a printf/out failure must be checked and
    routed through `die`, not ignored.

    chmod(0o444) would not make this fail for root or for any process with
    CAP_DAC_OVERRIDE (the default in a Docker container, and this script
    runs as root in production), so the write could succeed anyway and this
    test would pass without ever exercising the die() path. A directory at
    the summary's path fails the truncating write with EISDIR regardless of
    privilege level.
    """
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    unwritable = report_dir / "trivy-summary.txt"
    unwritable.mkdir()  # `: > "$summary"` must fail: can't open a dir for writing

    result, _, _, _ = _run(tmp_path, extra_env={"REPORT_DIR": str(report_dir)})

    assert result.returncode == 1
    assert "cannot write" in result.stderr
    assert "trivy-summary.txt" in result.stderr
