"""Tests for scripts/deployment/image-drift-check.py.

A fake `docker` on PATH answers `compose config`, `ps`, `inspect` and
`image inspect` from a JSON fixture, so the check runs its real logic with no
Docker daemon.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "deployment" / "image-drift-check.py"

FAKE_DOCKER = r"""#!/usr/bin/env python3
import json, os, sys
fx = json.load(open(os.environ["FAKE_FIXTURE"]))
a = sys.argv[1:]
if a[:2] == ["compose", "config"]:
    if fx.get("config_fail"):
        sys.exit(1)
    print(json.dumps(fx["config"])); sys.exit(0)
if a[0] == "ps":
    if fx.get("ps_fail"):
        sys.exit(1)
    # the script must scope to this project and exclude one-off containers
    assert "label=com.docker.compose.project=homelab" in a, a
    assert "label=com.docker.compose.oneoff=False" in a, a
    svc = [x.rsplit("=", 1)[1] for x in a if x.startswith("label=com.docker.compose.service=")][0]
    cid = fx["running"].get(svc)
    print(cid or ""); sys.exit(0)
if a[0] == "inspect":
    assert a[1:3] == ["--format", "{{.Image}}"], a
    print(fx["container_image"][a[-1]]); sys.exit(0)
if a[:2] == ["image", "inspect"]:
    assert a[2:4] == ["--format", "{{.Id}}"], a
    if fx.get("image_inspect_error"):
        print("permission denied while trying to connect to the Docker daemon", file=sys.stderr)
        sys.exit(1)
    ref = a[-1]
    if ref not in fx["local_images"]:
        print(f"Error: No such image: {ref}", file=sys.stderr)
        sys.exit(1)
    print(fx["local_images"][ref]); sys.exit(0)
sys.exit(3)
"""


def run(tmp_path, fixture, env_extra=None, path_override=None):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    docker = bindir / "docker"
    docker.write_text(FAKE_DOCKER)
    docker.chmod(0o755)
    fx = tmp_path / "fixture.json"
    fx.write_text(json.dumps(fixture))
    env = dict(os.environ)
    env["PATH"] = path_override or f"{bindir}{os.pathsep}{env['PATH']}"
    env["FAKE_FIXTURE"] = str(fx)
    env.pop("DEPLOY_ACCEPT_IMAGE_CHANGE", None)
    env["HOMELAB_OVERRIDE_LOG"] = str(tmp_path / "overrides.log")
    env.update(env_extra or {})
    return subprocess.run(
        ["python3", str(SCRIPT)], capture_output=True, text=True, env=env, cwd=tmp_path
    )


def base(**over):
    fx = {
        "config": {
            "name": "homelab",
            "services": {
                "web": {"image": "ghcr.io/x/web:latest"},
                "api": {"image": "ghcr.io/x/api:1.2"},
                "manager": {
                    "build": {"context": "."},
                    "image": "homelab-manager:local",
                },
            },
        },
        "running": {"web": "c-web", "api": "c-api", "manager": "c-mgr"},
        "container_image": {
            "c-web": "sha256:web-old",
            "c-api": "sha256:api",
            "c-mgr": "sha256:m1",
        },
        "local_images": {
            "ghcr.io/x/web:latest": "sha256:web-old",
            "ghcr.io/x/api:1.2": "sha256:api",
            "homelab-manager:local": "sha256:m2",
        },
    }
    fx.update(over)
    return fx


def test_no_change_passes(tmp_path):
    r = run(tmp_path, base())
    assert r.returncode == 0, r.stdout + r.stderr
    assert "no running container would change image" in r.stdout
    # guard against a vacuous pass: both image services were seen as running
    assert "not running" not in r.stdout


def test_moved_tag_blocks_the_deploy(tmp_path):
    fx = base()
    fx["local_images"]["ghcr.io/x/web:latest"] = "sha256:web-new"
    r = run(tmp_path, fx)
    assert r.returncode == 1
    assert "web: ghcr.io/x/web:latest (differs" in r.stdout
    assert "api:" not in r.stdout


def test_image_missing_locally_counts_as_a_change(tmp_path):
    fx = base()
    del fx["local_images"]["ghcr.io/x/api:1.2"]
    r = run(tmp_path, fx)
    assert r.returncode == 1
    assert "api: ghcr.io/x/api:1.2 (not on the host" in r.stdout


def test_accept_flag_lets_an_intended_change_through(tmp_path):
    fx = base()
    fx["local_images"]["ghcr.io/x/web:latest"] = "sha256:web-new"
    r = run(tmp_path, fx, {"DEPLOY_ACCEPT_IMAGE_CHANGE": "1"})
    assert r.returncode == 0
    assert "web:" in r.stdout and "proceeding" in r.stdout
    audit = (tmp_path / "overrides.log").read_text()
    assert "DEPLOY_ACCEPT_IMAGE_CHANGE=1 by" in audit
    assert "web: ghcr.io/x/web:latest" in audit


def test_build_services_are_skipped(tmp_path):
    # manager's running image differs from its local tag, but compose builds it
    r = run(tmp_path, base())
    assert r.returncode == 0
    assert "manager" not in r.stdout


def test_stopped_service_is_only_noted(tmp_path):
    fx = base()
    fx["running"]["web"] = None
    fx["local_images"]["ghcr.io/x/web:latest"] = "sha256:web-new"
    r = run(tmp_path, fx)
    assert r.returncode == 0
    assert "not running, will be started as resolved: web" in r.stdout


def test_compose_failure_cannot_be_mistaken_for_no_change(tmp_path):
    r = run(tmp_path, base(config_fail=True))
    assert r.returncode == 2


def test_ps_failure_is_a_check_error_not_a_pass(tmp_path):
    r = run(tmp_path, base(ps_fail=True))
    assert r.returncode == 2
    assert "docker ps failed" in r.stderr


def test_image_inspect_error_is_not_mistaken_for_absent(tmp_path):
    # a daemon/permission error must not become "compose would pull it",
    # which DEPLOY_ACCEPT_IMAGE_CHANGE=1 could then wave through
    r = run(
        tmp_path, base(image_inspect_error=True), {"DEPLOY_ACCEPT_IMAGE_CHANGE": "1"}
    )
    assert r.returncode == 2
    assert "docker image inspect failed" in r.stderr


def test_missing_docker_binary_is_a_check_error(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    # interpreter by absolute path, so PATH holds only the empty dir: a real
    # docker next to python3 (e.g. /usr/bin on the host) must not be reachable
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={"PATH": str(empty)},
    )
    assert r.returncode == 2
    assert "cannot run docker" in r.stderr
