#!/usr/bin/env python3
"""Read-only snapshot of the Cloudflare edge: tunnel ingress and DNS of the zones it serves.

The live tunnel ingress is remotely managed (Zero Trust dashboard), so git has no
record of which hostnames are public. This writes one, for disaster recovery and
drift checks against config/caddy/Caddyfile. It only issues GET requests.

The output is committed to a public repo, so it keeps structure and drops values
that should not be public: A/AAAA/TXT/MX contents are redacted and tunnel UUIDs are
replaced by tunnel names.

Usage (on the host, from the repo root):
    python3 scripts/maintenance/cloudflare-edge-snapshot.py > config/cloudflared/edge-snapshot.json

Reads CLOUDFLARE_API_TOKEN from the environment, else from ./.env. The account and
tunnel come from infra/terraform/terraform.tfvars (account_id, tunnel_id), or the
CF_ACCOUNT_ID / CF_TUNNEL_ID environment variables.
"""

import json
import os
import re
import sys
import urllib.request

API = "https://api.cloudflare.com/client/v4/"
REDACT_TYPES = {"A", "AAAA", "TXT", "MX", "SRV", "CAA"}


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
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
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

    cfg = get(tok, f"accounts/{account}/cfd_tunnel/{tunnel_id}/configurations")
    ingress = [
        {
            k: v
            for k, v in {
                "hostname": rule.get("hostname"),
                "path": rule.get("path"),
                "service": rule.get("service"),
                "httpHostHeader": (rule.get("originRequest") or {}).get(
                    "httpHostHeader"
                ),
            }.items()
            if v
        }
        for rule in ((cfg or {}).get("config") or {}).get("ingress", [])
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
                "<redacted>"
                if rec["type"] in REDACT_TYPES
                else tunnel_label(rec["content"])
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

    json.dump(
        {
            "tunnel": tunnels.get(tunnel_id, "<unknown>"),
            "ingress": ingress,
            "dns": zones,
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    print(
        f"ingress rules: {len(ingress)}; zones: "
        + ", ".join(f"{z} ({len(r)} records)" for z, r in zones.items()),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
