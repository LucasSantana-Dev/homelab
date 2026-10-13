"""wud-server.py must run the classify script baked into the agent-box image."""

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SERVER = REPO / "config" / "agent-box" / "wud-server.py"
DOCKERFILE = REPO / "Dockerfile.agent-box"


def _classify_cmd():
    tree = ast.parse(SERVER.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == "CLASSIFY_CMD" for t in node.targets
        ):
            return " ".join(ast.literal_eval(node.value))
    raise AssertionError("CLASSIFY_CMD not found")


def test_classify_never_runs_from_the_shared_workspace():
    # /workspace/homelab is the gate's workdir and can be on a PR branch.
    assert "/workspace" not in _classify_cmd()


def test_classify_script_is_baked_into_the_image():
    m = re.search(r"exec bash (\S+)", _classify_cmd())
    assert m, f"no 'exec bash <script>' in CLASSIFY_CMD: {_classify_cmd()!r}"
    path = m.group(1)
    copies = {
        dst: src
        for src, dst in re.findall(r"^COPY (\S+) (\S+)$", DOCKERFILE.read_text(), re.M)
    }
    assert copies.get(path) == "scripts/agent-tasks/hermes-wud-classify.sh"
