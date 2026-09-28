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

import getpass
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

OVERRIDE_LOG = os.environ.get(
    "HOMELAB_OVERRIDE_LOG", "/var/log/homelab-deploy-overrides.log"
)


class CheckError(RuntimeError):
    """The check itself could not run; never treated as "no change"."""


def run(*args):
    try:
        r = subprocess.run(args, capture_output=True, text=True)
    except OSError as e:  # docker missing or not executable
        raise CheckError(f"cannot run {args[0]}: {e}") from e
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def local_image_id(ref):
    """Image ID for ref, None when Docker confirms it is not on the host."""
    rc, out, err = run("docker", "image", "inspect", "--format", "{{.Id}}", ref)
    if rc == 0 and out:
        return out
    if "no such image" in err.lower():
        return None
    raise CheckError(f"docker image inspect failed for {ref}: {err or rc}")


def audit_override(changes):
    """Record DEPLOY_ACCEPT_IMAGE_CHANGE like the DEPLOY_FORCE override."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [f"[{stamp}] DEPLOY_ACCEPT_IMAGE_CHANGE=1 by {getpass.getuser()}\n"]
    lines += [f"  {name}: {ref} ({why})\n" for name, ref, why in changes]
    try:
        with open(OVERRIDE_LOG, "a", encoding="utf-8") as f:
            f.writelines(lines)
    except OSError:
        try:
            subprocess.run(
                ["sudo", "-n", "tee", "-a", OVERRIDE_LOG],
                input="".join(lines),
                text=True,
                capture_output=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            print(
                f"   ⚠️  could not write the override to {OVERRIDE_LOG}",
                file=sys.stderr,
            )


def running_image(project, service):
    rc, ids, _ = run(
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
        raise CheckError(f"docker ps failed for {service}")
    if not ids:
        return None
    rc, image, _ = run("docker", "inspect", "--format", "{{.Image}}", ids.split()[0])
    if rc != 0 or not image:
        raise CheckError(f"docker inspect failed for {service}")
    return image


def main():
    try:
        rc, out, _ = run("docker", "compose", "config", "--format", "json")
    except CheckError as e:
        print(f"❌ image-drift-check: {e}", file=sys.stderr)
        return 2
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
            resolved = local_image_id(ref)
            if resolved is None:
                changes.append((name, ref, "not on the host, compose would pull it"))
            elif resolved != current:
                changes.append(
                    (name, ref, "differs from the running container's image")
                )
    except CheckError as e:
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
        print(f"   DEPLOY_ACCEPT_IMAGE_CHANGE=1: proceeding (logged to {OVERRIDE_LOG})")
        audit_override(changes)
        return 0
    print("")
    print("   Test each one first, isolated from the stack, e.g.:")
    print("     docker run --rm --network none <image>   (it must start, not crash)")
    print("   Then pin a known-good tag: set the service's IMG_* variable in .env")
    print(
        "   when its compose image line has one, otherwise pin the tag in the compose"
    )
    print("   file. Or accept the change (audited):")
    print("     DEPLOY_ACCEPT_IMAGE_CHANGE=1 make deploy")
    return 1


if __name__ == "__main__":
    sys.exit(main())
