"""wud-server.py must run the classify script baked into the agent-box image
and refuse callers without the shared token."""

import ast
import importlib.util
import io
import re
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SERVER = REPO / "config" / "agent-box" / "wud-server.py"
DOCKERFILE = REPO / "Dockerfile.agent-box"
# Test value only; long enough to pass MIN_TOKEN_LEN.
TEST_TOKEN = "x" * 40


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


def _load_server():
    spec = importlib.util.spec_from_file_location("wud_server", SERVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_read_token_rejects_short_or_missing():
    mod = _load_server()
    assert mod.read_token(io.StringIO("")) is None
    assert mod.read_token(io.StringIO("short\n")) is None
    assert mod.read_token(io.StringIO(TEST_TOKEN + "\n")) == TEST_TOKEN.encode()


def test_main_exits_without_token(monkeypatch):
    mod = _load_server()
    monkeypatch.setattr(mod.sys, "stdin", io.StringIO(""))
    with pytest.raises(SystemExit):
        mod.main()


@pytest.fixture
def server_url():
    mod = _load_server()
    mod.Handler.token = TEST_TOKEN.encode()
    # Never run the real classifier from a test.
    mod.CLASSIFY_CMD = ["true"]
    srv = HTTPServer(("127.0.0.1", 0), mod.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/wud-classify"
    srv.shutdown()
    srv.server_close()


def _post(url, headers):
    req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # nosec B310
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


@pytest.mark.parametrize("headers", [{}, {"X-Classify-Token": "wrong"}])
def test_post_without_valid_token_is_401(server_url, headers):
    assert _post(server_url, headers) == 401


def test_post_with_token_is_200(server_url):
    assert _post(server_url, {"X-Classify-Token": TEST_TOKEN}) == 200
