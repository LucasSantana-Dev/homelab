# Homelab Access Layers

Single source of truth for **which service is reachable via which path**.
Resolves the ambiguity between Cloudflare Tunnel, Tailscale, and LAN.

## The three layers

| Layer | Hostname pattern | Auth | Audience | When to use |
|---|---|---|---|---|
| **LAN** | `*.home` | None (physical presence) | Household on Wi-Fi | Low-friction in-home use |
| **Tailscale** | `*.homelab.example.com` · `<hostname>.<tailnet>.ts.net` | Tailscale identity | Self + close friends | Private remote access, admin tasks |
| **Cloudflare Tunnel** | `*.luk-homeserver.com.br` | Cloudflare Access policy | Public internet (with auth) | Services that need to be reachable without installing Tailscale |

## Invariant — DNS guardrail

**A hostname belongs to exactly one layer.** Do not publish a Tailscale
DNS A record for a hostname that's already routed through Cloudflare
Tunnel — clients would resolve to the origin IP, bypass Cloudflare
Access, and hit TLS-cert mismatch errors.

- `*.luk-homeserver.com.br` → **Cloudflare only**. No Tailscale records.
- `*.homelab.example.com` → **Tailscale only**. No public DNS.
- `*.home` → **Pi-hole local** only. Never publish externally.

(This encodes the existing guardrail from `cloudflare-tunnel-phase1.md`.)

## Service × layer matrix

| Service | LAN | Tailscale | CF Tunnel | Notes |
|---|---|---|---|---|
| Homepage dashboard | `homelab.home` | `homelab.homelab.example.com` | `luk-homeserver.com.br` + `www.*` | Entrypoint, all three layers |
| Home Assistant | — | `ha.homelab.example.com` | `homeassistant.luk-homeserver.com.br` | CF Access policy required |
| Jellyfin | — | Tailscale direct :8096 | — | Friends path; see `tailscale-friends-sharing.md` |
| Stremio | `stremio.home` | Tailscale direct :11470 | — | Friends path |
| Craftvaria (Minecraft) | — | Tailscale direct :25565 | — | TCP, not HTTPS — CF Tunnel can't help |
| Grafana | — | via `tailscale serve` | `grafana.luk-homeserver.com.br` | CF Access gated |
| Portainer | — | via `tailscale serve` | `portainer.luk-homeserver.com.br` | CF Access gated (critical) |
| n8n | — | via `tailscale serve` | `n8n.luk-homeserver.com.br` | CF Access gated |
| Nextcloud | — | `cloud.homelab.example.com` | `cloud.luk-homeserver.com.br` | Primary public access via CF |
| Paperless-ngx | — | via `tailscale serve` | `docs.luk-homeserver.com.br` | CF Access gated |
| Vaultwarden | — | — | `vault.luk-homeserver.com.br` | CF Access policy MUST be strict |
| Authentik | — | — | `auth.luk-homeserver.com.br` | SSO broker — CF path only |
| Pi-hole admin | `pihole.home` | `pihole.homelab.example.com` | — | Never public |
| Prometheus | — | `prom.homelab.example.com` | — | Never public |
| Netdata | — | `netdata.homelab.example.com` | — | Never public; candidate for removal (audit PR #28) |
| cAdvisor | — | `cadvisor.homelab.example.com` | — | Never public |
| Alertmanager | — | `alerts.homelab.example.com` | — | Never public |
| Cockpit (host OS) | `cockpit.home` | via Tailscale SSH | — | Physical-access tier |
| Container registry | `registry.home` | `registry.homelab.example.com` | — | Never public |
| Lucky bot dashboard | `lucky.home` | `lucky.homelab.example.com` | — | Internal |
| forge-mcp-gateway | — | Tailscale direct | — | Profile-gated; dev-only |

Services in CF Tunnel config (`config/cloudflared/config.yml`) but
*not* in the phase-1 "included" list (e.g. `blackbox`, `pihole`,
`prometheus`) are **ingressed but blocked by CF Access policy**. See
the phase-1 doc for the full allow-list.

## Layer-choice rules

- **Needs browser access from anywhere** → CF Tunnel + Access policy.
- **Needs raw-TCP access** (Minecraft, SSH) → Tailscale.
- **Needs zero-config guest access** (close friends) → Tailscale node sharing.
- **Only used inside the house** → LAN `*.home`.
- **Admin-only** → Tailscale (never CF Tunnel, even gated).

## Current open gaps / action items

- [ ] Tunnel status: `luk-homeserver.com.br` returned **Error 1033**
      at 2026-04-19T17:50Z. Diagnose per
      `scripts/diagnose-cloudflare-tunnel.sh` (to add).
- [ ] Verify `.env` has a real digest for `IMG_CLOUDFLARED`, not the
      `<digest>` placeholder from `.env.example`.
- [ ] Verify `CF_TUNNEL_TOKEN` is populated in production `.env`.
- [ ] Split-DNS: add `*.homelab.example.com` A records in Tailscale
      admin DNS (per `tailscale-dns-records-setup.md`) — these don't
      conflict with CF because the domain is different.
- [ ] Enforce the invariant in CI: a lint script that fails if a
      hostname appears in both `tailscale/dns-records.json` and
      `config/cloudflared/config.yml`.

## Related docs

- `cloudflare-tunnel-phase1.md` — public hostname allow-list.
- `tailscale-setup.md` — base Tailscale config.
- `tailscale-friends-sharing.md` — friend onboarding.
- `tailscale-features-checklist.md` — full Tailscale activation.
- `tailscale-dns-records-setup.md` — Tailscale MagicDNS records.
- `network-architecture.md` — legacy three-tier model (superseded by this doc).
