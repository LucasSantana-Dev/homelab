#!/usr/bin/env python3
"""Fail when a public hostname is not gated by Cloudflare Access and is not allowlisted.

Reads the tunnel ingress recorded in config/cloudflared/edge-snapshot.json (ADR
0041) and, for every real hostname in it, makes one unauthenticated HTTPS
request from outside with no redirects followed. A hostname is "gated" when the
response is 302 or 303 with a Location on *.cloudflareaccess.com (the Cloudflare
Access login redirect). Every hostname must be gated, unless it is listed with a
reason in config/cloudflared/access-allowlist.txt (mirrors the style of
config/caddy/public-no-auth.txt, enforced the same way by
scripts/security/caddy-auth-lint.py): one host per line, then a REQUIRED reason
for why it is intentionally public.

Only entries carrying a real "hostname" are probed. The trailing hostless rule
(the tunnel's 404 catch-all) is not a hostname and is skipped. A wildcard entry
(hostname starting with "*.") routes every undeclared name in its zone to the
origin, so the check probes one random subdomain under it and requires that to
be gated too; a wildcard cannot be allowlisted. DNS-only records
(MX, TXT, and similar at the zone apex) never appear in `ingress` and carry no
HTTP traffic through the tunnel, so they are out of scope by construction.

Two mismatches make the check fail:
  - a public hostname (not gated) that is not on the allowlist: a coverage gap.
  - an allowlisted hostname that IS gated: the allowlist entry is stale (the
    Cloudflare Access app now covers it, or the bypass policy is gone).
An allowlist entry for a hostname no longer in the snapshot's ingress is also
an error (the host was removed or renamed; the entry should follow it).

A network error (timeout, DNS failure, connection refused, TLS error) is
always a failure, never treated as "must be gated" or silently skipped: an
edge that cannot be reached is not verified access control.

Usage: access-coverage-check.py [snapshot.json] [allowlist.txt]
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

SNAPSHOT = "config/cloudflared/edge-snapshot.json"
ALLOWLIST = "config/cloudflared/access-allowlist.txt"
ACCESS_SUFFIX = ".cloudflareaccess.com"
TIMEOUT = 10
SCHEME = "https"  # tests point this at a local http server
USER_AGENT = "homelab-access-coverage-check/1.0"


class ProbeResult:
    """Outcome of one unauthenticated request: gated, plain response, or error."""

    def __init__(
        self, status=None, location_host=None, location_scheme=None, error=None
    ):
        self.status = status
        self.location_host = location_host
        self.location_scheme = location_scheme
        self.error = error

    @property
    def gated(self):
        # The Cloudflare Access login redirect is always https. A Location
        # with a matching host but another scheme (ftp://, or none captured)
        # is not a real Access redirect and must not count as gated.
        return (
            self.error is None
            and self.status in (302, 303)
            and self.location_host is not None
            and self.location_host.endswith(ACCESS_SUFFIX)
            and self.location_scheme == "https"
        )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        return None  # stop urllib from following; the 3xx is inspected instead


_OPENER = urllib.request.build_opener(_NoRedirect)


def probe(hostname, timeout=TIMEOUT):
    """Make one unauthenticated HTTPS GET to hostname, no redirects followed."""
    req = urllib.request.Request(
        f"{SCHEME}://{hostname}/", headers={"User-Agent": USER_AGENT}
    )
    try:
        # hostname always comes from our own edge-snapshot.json, not user input.
        with _OPENER.open(req, timeout=timeout) as resp:  # nosec B310
            return ProbeResult(status=resp.getcode())
    except urllib.error.HTTPError as e:
        location = e.headers.get("Location") if e.headers else None
        parsed = urllib.parse.urlparse(location) if location else None
        host = parsed.hostname if parsed else None
        scheme = parsed.scheme if parsed else None
        return ProbeResult(status=e.code, location_host=host, location_scheme=scheme)
    except Exception as e:  # noqa: BLE001 - any network failure is a failure
        return ProbeResult(error=str(e))


def load_snapshot(path, errors):
    """Return (hosts, skipped_wildcards) from the ingress list, in order.

    A missing, non-list, or empty `ingress` must fail closed: with nothing to
    probe, `check()` would otherwise return zero errors and pass silently,
    turning a truncated or malformed snapshot into a false "all covered"
    instead of the coverage gap it actually is.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    ingress = data.get("ingress")
    if not isinstance(ingress, list) or not ingress:
        errors.append(
            f"{path}: 'ingress' is missing, not a list, or empty; "
            "cannot verify access coverage without it (failing closed)"
        )
        return [], []
    hosts, wildcards = [], []
    for rule in ingress:
        hostname = rule.get("hostname") if isinstance(rule, dict) else None
        if not hostname:
            continue  # the hostless catch-all rule
        if hostname.startswith("*."):
            wildcards.append(hostname)
            continue
        hosts.append(hostname)
    return hosts, wildcards


def load_allowlist(path, errors):
    hosts = {}
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            entry, _, reason = line.partition("#")
            entry = entry.strip()
            if not entry:
                continue
            if not reason.strip():
                errors.append(
                    f"{path}:{n}: {entry} has no reason; add `# <why it is intentionally public>`"
                )
            hosts[entry] = n
    return hosts


def check(snapshot_path, allowlist_path):
    errors, notes = [], []
    hosts, wildcards = load_snapshot(snapshot_path, errors)
    # A wildcard rule routes every unlisted name in the zone to the origin, so
    # a subdomain nobody declared is reachable. Probe a random one: it must be
    # gated. Wildcards cannot be allowlisted.
    for wildcard in wildcards:
        sample = f"access-check-{uuid.uuid4().hex[:12]}.{wildcard[2:]}"
        result = probe(sample)
        if result.error is not None:
            errors.append(
                f"{wildcard}: network error probing {sample}, treated as a failure: {result.error}"
            )
        elif not result.gated:
            errors.append(
                f"{wildcard}: unlisted subdomain {sample} is public (HTTP {result.status}); "
                "the wildcard exposes every undeclared name, gate the zone in Cloudflare Access"
            )
        else:
            notes.append(
                f"{wildcard}: random subdomain {sample} redirects to Cloudflare Access"
            )
    allowed = load_allowlist(allowlist_path, errors)
    host_set = set(hosts)

    for hostname in hosts:
        result = probe(hostname)
        if result.error is not None:
            errors.append(
                f"{hostname}: network error, treated as a failure: {result.error}"
            )
            continue
        if hostname in allowed:
            if result.gated:
                errors.append(
                    f"{hostname}: allowlisted as intentionally public ({allowlist_path}:{allowed[hostname]}) "
                    f"but redirects to Cloudflare Access ({result.location_host}); "
                    "the allowlist entry is stale, remove it or confirm the bypass policy"
                )
        else:
            if not result.gated:
                detail = f"HTTP {result.status}"
                if result.location_host:
                    detail += f", Location host {result.location_host}"
                errors.append(
                    f"{hostname}: public and not allowlisted ({detail}); "
                    f"add it to {allowlist_path} with a reason, or fix the Cloudflare Access app coverage"
                )

    for hostname, n in sorted(allowed.items(), key=lambda kv: kv[1]):
        if hostname not in host_set:
            errors.append(
                f"{allowlist_path}:{n}: {hostname} is not in {snapshot_path}'s ingress; remove it"
            )

    return errors, notes


def main():
    snapshot_path = sys.argv[1] if len(sys.argv) > 1 else SNAPSHOT
    allowlist_path = sys.argv[2] if len(sys.argv) > 2 else ALLOWLIST
    errors, notes = check(snapshot_path, allowlist_path)
    for note in notes:
        print(note, file=sys.stderr)
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print("access coverage check passed", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
