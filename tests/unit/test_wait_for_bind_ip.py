"""Tests for scripts/maintenance/wait-for-bind-ip.sh.

A fake `ip` on PATH reports the BIND_IP address only after a number of calls,
so the wait loop runs for real without touching the host's interfaces. `sleep`
is faked too so the tests take no wall-clock time.
"""

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "maintenance" / "wait-for-bind-ip.sh"

FAKE_IP = """#!/bin/bash
n=$(cat "$COUNTER" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$COUNTER"
echo "1: lo    inet 127.0.0.1/8 scope host lo"
if [ "$n" -ge "$APPEAR_AFTER" ]; then
  echo "5: tailscale0    inet 100.95.204.103/32 scope global tailscale0"
fi
"""


def run(tmp_path, env_line, appear_after=1, timeout=5):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "ip").write_text(FAKE_IP)
    (bindir / "sleep").write_text("#!/bin/bash\nexit 0\n")
    for f in ("ip", "sleep"):
        (bindir / f).chmod(0o755)
    env_file = tmp_path / "env"
    env_file.write_text(f"OTHER=1\n{env_line}\n")
    env = dict(os.environ)
    env.update(
        PATH=f"{bindir}{os.pathsep}{env['PATH']}",
        ENV_FILE=str(env_file),
        WAIT_BIND_IP_TIMEOUT=str(timeout),
        COUNTER=str(tmp_path / "count"),
        APPEAR_AFTER=str(appear_after),
    )
    r = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env)
    calls = (
        int((tmp_path / "count").read_text()) if (tmp_path / "count").exists() else 0
    )
    return r, calls


def test_address_already_up_returns_at_once(tmp_path):
    r, calls = run(tmp_path, "BIND_IP=100.95.204.103")
    assert r.returncode == 0
    assert "is up after 0s" in r.stdout
    assert calls == 1


def test_waits_until_the_address_appears(tmp_path):
    r, calls = run(tmp_path, "BIND_IP=100.95.204.103", appear_after=4)
    assert r.returncode == 0
    assert "is up after 3s" in r.stdout
    assert calls == 4


def test_loopback_needs_no_wait(tmp_path):
    r, calls = run(tmp_path, "BIND_IP=127.0.0.1")
    assert r.returncode == 0
    assert calls == 0


def test_quoted_value_is_understood(tmp_path):
    r, _ = run(tmp_path, 'BIND_IP="100.95.204.103"')
    assert "is up after 0s" in r.stdout


def test_timeout_warns_but_never_fails_the_unit(tmp_path):
    r, calls = run(tmp_path, "BIND_IP=100.95.204.103", appear_after=99, timeout=3)
    assert r.returncode == 0
    assert "not assigned after 3s" in r.stderr
    assert calls == 3


def test_does_not_match_a_longer_address(tmp_path):
    # 100.95.204.10 must not be satisfied by 100.95.204.103 being present
    r, calls = run(tmp_path, "BIND_IP=100.95.204.10", timeout=2)
    assert "not assigned after 2s" in r.stderr
