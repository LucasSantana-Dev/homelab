# Sharing Homelab Services with Friends

How to give personal contacts access to **Jellyfin, Stremio, and the
Craftvaria Minecraft server** — without exposing admin panels, metrics,
SSH, or Pi-hole.

No public internet exposure. No Cloudflare Tunnel. No seats billed.

## TL;DR

1. Tag the homelab host: `sudo tailscale up --advertise-tags=tag:homelab-friends-exposed --reset`.
2. Apply the ACL in [`../tailscale/acl.hujson`](../tailscale/acl.hujson) via
   https://login.tailscale.com/admin/acls.
3. Share the host from the admin console (**Machines → Share**) with each
   friend's Tailscale email.
4. Friend installs Tailscale on their device → accepts invite → reaches
   `jellyfin.homelab.example.com`, `stremio.homelab.example.com`,
   or the Minecraft server on `100.64.0.10:25565`.

## Why this instead of Cloudflare Funnel / public DNS?

| Option                  | Auth                | Blast radius          | Cost        |
|-------------------------|---------------------|-----------------------|-------------|
| Tailscale node sharing  | Per-identity invite | Ports in ACL only     | Free        |
| Tailscale Funnel        | **None (public)**   | Whatever you publish  | Free        |
| Cloudflare Tunnel       | Needs Access policy | Per-hostname          | Free + conf |
| Port forward + password | Weak                | Full service          | Free        |

For "close friends" — node sharing wins on auth + blast radius.

## Architecture

```
Friend's device
   │ Tailscale (their own tailnet)
   ▼
shared node: homelab (tag:homelab-friends-exposed)
   │ ACL: only ports 8096/8920/11470/12470/25565
   ▼
Jellyfin · Stremio · Craftvaria
```

Everything else on the homelab (Grafana, Prometheus, Pi-hole admin,
Portainer, Cockpit, SSH, Home Assistant, Nextcloud, registry) stays
inaccessible to friends — the ACL has no rule granting `group:friends`
or `autogroup:shared` access to those ports.

## Onboarding runbook

### One-time setup (you)

```bash
# 1. Tag the homelab host
sudo tailscale up --advertise-tags=tag:homelab-friends-exposed --reset

# 2. Verify
tailscale status | grep homelab
```

Then in the admin console (one-time):

1. **Access controls** → paste `tailscale/acl.hujson` → **Save**.
   (Or enable GitHub sync so `main` is the source of truth.)
2. **Machines** → homelab → confirm tag appears.

### Adding a friend

1. Ask for their Tailscale email (must have a free account at
   https://tailscale.com).
2. Admin console → **Machines** → homelab → **Share this machine** →
   enter email → **Send invite**.
3. They accept the invite from their email / admin console.
4. They install Tailscale on their device (iOS/Android/desktop) and
   sign into their own account — not yours.
5. Send them the service URLs / host (see below).

### Service URLs for friends

Friends use **MagicDNS** names if their Tailscale app has it enabled
(default), otherwise the raw Tailscale IP.

| Service    | MagicDNS name                         | Direct IP         | Port  |
|------------|---------------------------------------|-------------------|-------|
| Jellyfin   | `http://homelab.<your-tailnet>.ts.net:8096` | `100.64.0.10:8096` | 8096  |
| Stremio    | `http://homelab.<your-tailnet>.ts.net:11470`| `100.64.0.10:11470`| 11470 |
| Craftvaria | `homelab.<your-tailnet>.ts.net`       | `100.64.0.10`     | 25565 |

Tell the friend: "Install Tailscale, accept the invite, then open Jellyfin
at the URL above."

### Revoking access

- **Single friend:** admin console → **Sharing** → revoke that machine share.
- **All friends at once:** remove the `tag:homelab-friends-exposed` tag
  from the homelab host (`tailscale up --advertise-tags=""`) — the ACL
  still exists but has nothing to match. Put the tag back to re-enable.

### Audit

Admin console → **Logs** shows every friend connection with timestamp,
source identity, destination port. Review monthly.

## Limits

- Free plan allows sharing nodes with up to 3 external users. Upgrade
  or switch to guest-user model (Path B in `tailscale/README.md`) if you
  need more.
- Friends must install Tailscale on each device they want access from.
  There is no browser-only option — that's the tradeoff for authenticated,
  non-public access.

## Related

- [`tailscale-setup.md`](tailscale-setup.md) — base Tailscale-only config.
- [`tailscale-dns-records-setup.md`](tailscale-dns-records-setup.md) — MagicDNS records.
- [`network-architecture.md`](network-architecture.md) — service-tier classification.
- [`../tailscale/acl.hujson`](../tailscale/acl.hujson) — authoritative ACL policy.
