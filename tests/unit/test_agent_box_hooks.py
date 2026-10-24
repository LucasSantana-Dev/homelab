"""Tests for the agent-box guardrail hook config/agent-box/protect-homelab.sh."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "config/agent-box/protect-homelab.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None, reason="hook parses tool input with jq"
)


def run_hook(command):
    payload = json.dumps({"tool_input": {"command": command}})
    return subprocess.run(
        ["bash", str(HOOK)], input=payload, capture_output=True, text=True
    )


@pytest.mark.parametrize(
    "command",
    [
        "docker stop lucky-bot",
        "docker rm -f nextcloud",
        "docker kill pihole",
        "docker restart lucky_backend",
        "docker container stop cloudflared",
        "cd /workspace && docker stop homeassistant",
    ],
)
def test_blocks_protected_container(command):
    result = run_hook(command)
    assert result.returncode == 2
    assert "BLOCK" in result.stderr


@pytest.mark.parametrize(
    "command",
    ["docker stop my-scratch", "docker ps", "ls -la", ""],
)
def test_allows_unprotected(command):
    assert run_hook(command).returncode == 0
