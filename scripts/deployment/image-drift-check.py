#!/usr/bin/env python3
"""Stop `make deploy` from silently swapping a running container's image.

`docker compose up -d` recreates any container whose resolved config differs
from the running one. When a service tracks a mutable tag (`:latest`), a
long-lived container can keep an older image while the tag moves on to a
build that has never run in production. On 2026-09-28 a deploy that only
changed CHANGELOG recreated cojam-web on such a `:latest`, which crashed at
start (MODULE_NOT_FOUND) and took the site down for about 35 minutes.

For every image-based service (services with `build:` are skipped), compare
the image ID of its running container with the image the compose file
resolves to right now. A service whose image would change is listed and the
deploy stops, unless DEPLOY_ACCEPT_IMAGE_CHANGE=1 says the change is
intended. A resolved image that is not on the host counts as a change too:
compose would pull it. Services with no running container are only noted,
since starting a stopped service is what a deploy is for.

Exit codes: 0 no image change (or accepted), 1 change found, 2 cannot check.
"""

import json
import os
import subprocess
import sys


def run(*args):
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def running_image(project, service):
    rc, ids = run(
        "docker",
        "ps",
        "-q",
        "--filter",
        f"label=com.docker.compose.project={project}",
        "--filter",
        f"label=com.docker.compose.service={service}",
        "--filter",
        "label=com.docker.compose.oneoff=False",
    )
    if rc != 0:
        raise RuntimeError(f"docker ps failed for {service}")
    if not ids:
        return None
    rc, image = run("docker", "inspect", "--format", "{{.Image}}", ids.split()[0])
    if rc != 0 or not image:
        raise RuntimeError(f"docker inspect failed for {service}")
    return image


def main():
    rc, out = run("docker", "compose", "config", "--format", "json")
    if rc != 0:
        print("❌ image-drift-check: `docker compose config` failed", file=sys.stderr)
        return 2
    try:
        cfg = json.loads(out)
        services = cfg["services"]
    except (ValueError, KeyError, TypeError):
        print(
            "❌ image-drift-check: could not parse the compose config", file=sys.stderr
        )
        return 2
    project = cfg.get("name") or os.path.basename(os.getcwd())

    changes, stopped = [], []
    try:
        for name in sorted(services):
            spec = services[name] or {}
            if "build" in spec or not spec.get("image"):
                continue
            ref = spec["image"]
            current = running_image(project, name)
            if current is None:
                stopped.append(name)
                continue
            rc, resolved = run("docker", "image", "inspect", "--format", "{{.Id}}", ref)
            if rc != 0 or not resolved:
                changes.append((name, ref, "not on the host, compose would pull it"))
            elif resolved != current:
                changes.append(
                    (name, ref, "differs from the running container's image")
                )
    except RuntimeError as e:
        print(f"❌ image-drift-check: {e}", file=sys.stderr)
        return 2

    if stopped:
        print(f"  note: not running, will be started as resolved: {', '.join(stopped)}")
    if not changes:
        print("  ✓ image-drift-check: no running container would change image")
        return 0

    print("⚠️  This deploy would change the image of running containers:")
    for name, ref, why in changes:
        print(f"   {name}: {ref} ({why})")
    if os.environ.get("DEPLOY_ACCEPT_IMAGE_CHANGE") == "1":
        print("   DEPLOY_ACCEPT_IMAGE_CHANGE=1: proceeding")
        return 0
    print("")
    print("   Test each one first, isolated from the stack, e.g.:")
    print("     docker run --rm --network none <image>   (it must start, not crash)")
    print(
        "   Then pin a known-good tag with IMG_<SERVICE> in .env, or accept the change:"
    )
    print("     DEPLOY_ACCEPT_IMAGE_CHANGE=1 make deploy")
    return 1


if __name__ == "__main__":
    sys.exit(main())
