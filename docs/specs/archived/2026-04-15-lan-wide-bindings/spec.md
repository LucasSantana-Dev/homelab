---
status: shipped
created: 2026-04-15
shipped: 2026-04-15
owner: lucassantana
pr: https://github.com/LucasSantana-Dev/homelab/pull/9
tags: network,caddy,pihole
---

# lan-wide-bindings

## Goal
Make every homelab service reachable from the LAN (192.168.0.0/24), not only via Tailscale.

## Approach
- Configurable `${BIND_IP:-0.0.0.0}` replacing `${TAILSCALE_IP}` across compose modules.
- Caddy LAN reverse proxy with *.home hostnames (host network, :80).
- Pi-hole v6 with FTLCONF_dns_listeningMode=all, wildcard *.home → 192.168.0.11.
- Patched k3s traefik svc to ClusterIP (Klipper LB was stealing :80).
- systemd-resolved stub listener disabled so Pi-hole can bind :53.

## Verification
- `dig @192.168.0.11 ai.home` → 192.168.0.11.
- 7/7 *.home hostnames smoke-tested from LAN client.
