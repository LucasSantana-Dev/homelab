#!/usr/bin/env python3
"""Read-only snapshot of the Cloudflare edge: tunnel ingress and DNS of the zones it serves.

The live tunnel ingress is remotely managed (Zero Trust dashboard), so git has no
record of which hostnames are public. This writes one, for disaster recovery and
drift checks against config/caddy/Caddyfile. It only issues GET requests.

The output is committed to a public repo, so record contents are an allowlist:
only CNAME targets are kept (tunnel UUIDs replaced by tunnel names); every other
record type, including ones added to Cloudflare later, is written as <redacted>.

Usage (on the host, from the repo root):
    python3 scripts/maintenance/cloudflare-edge-snapshot.py config/cloudflared/edge-snapshot.json

The file is replaced only after every request succeeded, so a network or token
error leaves the previous snapshot in place. Reads CLOUDFLARE_API_TOKEN from the
environment, else from ./.env. The account and tunnel come from
infra/terraform/terraform.tfvars (account_id, tunnel_id), or the CF_ACCOUNT_ID /
CF_TUNNEL_ID environment variables.
"""

import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request

API = "https://api.cloudflare.com/client/v4/"
KEEP_CONTENT_TYPES = {"CNAME"}


def setting(name, env_key, pattern):
    if os.environ.get(env_key):
        return os.environ[env_key]
    path = "infra/terraform/terraform.tfvars"
    if os.path.exists(path):
        m = re.search(pattern, open(path).read(), re.M)
        if m:
            return m.group(1)
    sys.exit(f"missing {name}: set {env_key} or add it to {path}")


def token():
    if os.environ.get("CLOUDFLARE_API_TOKEN"):
        return os.environ["CLOUDFLARE_API_TOKEN"]
    if os.path.exists(".env"):
        for line in open(".env"):
            if line.startswith("CLOUDFLARE_API_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"')
    sys.exit("missing CLOUDFLARE_API_TOKEN (environment or ./.env)")


def get(tok, path):
    out, page = [], 1
    while True:
        sep = "&" if "?" in path else "?"
        req = urllib.request.Request(
            f"{API}{path}{sep}per_page=100&page={page}",
            headers={"Authorization": f"Bearer {tok}"},
        )
        try:
            # The URL always starts with the constant https API base above.
            with urllib.request.urlopen(req, timeout=30) as r:  # nosec B310
                body = json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            sys.exit(f"GET {path} failed: {e}")
        if not body.get("success"):
            sys.exit(f"GET {path} failed: {body.get('errors')}")
        result = body["result"]
        if not isinstance(result, list):
            return result
        out += result
        info = body.get("result_info") or {}
        if page >= info.get("total_pages", 1):
            return out
        page += 1


def main():
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <output.json>")
    out_path = sys.argv[1]
    tok = token()
    account = setting("account_id", "CF_ACCOUNT_ID", r'^account_id\s*=\s*"([^"]+)"')
    tunnel_id = setting("tunnel_id", "CF_TUNNEL_ID", r'^tunnel_id\s*=\s*"([^"]+)"')

    tunnels = {
        t["id"]: t["name"]
        for t in get(tok, f"accounts/{account}/cfd_tunnel?is_deleted=false")
    }

    def tunnel_label(value):
        for tid, name in tunnels.items():
            value = value.replace(tid, f"<tunnel:{name}>")
        return value

    cfg = (
        get(tok, f"accounts/{account}/cfd_tunnel/{tunnel_id}/configurations") or {}
    ).get("config") or {}
    ingress = [
        {
            k: v
            for k, v in {
                "hostname": rule.get("hostname"),
                "path": rule.get("path"),
                "service": rule.get("service"),
                "originRequest": rule.get("originRequest"),
            }.items()
            if v
        }
        for rule in cfg.get("ingress", [])
    ]

    # Only zones this tunnel serves: the token also reads unrelated zones (other
    # projects), and their records do not belong in the homelab's public repo.
    hosts = [r["hostname"] for r in ingress if "hostname" in r]
    zones = {}
    for zone in sorted(get(tok, "zones"), key=lambda z: z["name"]):
        if not any(h == zone["name"] or h.endswith("." + zone["name"]) for h in hosts):
            continue
        records = []
        for rec in get(tok, f"zones/{zone['id']}/dns_records"):
            content = (
                tunnel_label(rec["content"])
                if rec["type"] in KEEP_CONTENT_TYPES
                else "<redacted>"
            )
            records.append(
                {
                    "name": rec["name"],
                    "type": rec["type"],
                    "content": content,
                    "proxied": rec.get("proxied", False),
                }
            )
        zones[zone["name"]] = sorted(records, key=lambda r: (r["name"], r["type"]))

    snapshot = {
        "tunnel": tunnels.get(tunnel_id, "<unknown>"),
        "originRequest": cfg.get("originRequest") or {},
        "ingress": ingress,
        "dns": zones,
    }
    out_dir = os.path.dirname(os.path.abspath(out_path))
    with tempfile.NamedTemporaryFile(
        "w", dir=out_dir, delete=False, suffix=".tmp"
    ) as f:
        json.dump(snapshot, f, indent=2)
        f.write("\n")
    os.replace(f.name, out_path)
    print(
        f"ingress rules: {len(ingress)}; zones: "
        + ", ".join(f"{z} ({len(r)} records)" for z, r in zones.items()),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
