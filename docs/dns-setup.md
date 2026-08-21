# DNS Setup Guide for Homelab

## Overview

The homelab uses custom domains like `auth.homelab.example.com` that need DNS resolution to work properly. Since all services are bound to your Tailscale IP (see `TAILSCALE_IP` in `.env`), you have several options for DNS configuration.

## Option 1: Tailscale MagicDNS (Recommended)

**Pros:**

- Works across all devices on your Tailscale network
- No manual configuration needed on client machines
- Automatic updates when IP changes
- Most reliable solution

**Setup Steps:**

1. Access your Tailscale admin console at <https://login.tailscale.com/admin/dns>

2. Navigate to **DNS** settings

3. Add a nameserver:
   - Type: Custom
   - Address: `100.100.100.100` (Tailscale's built-in DNS)

4. Add DNS records for your domain:

   ```
   homelab.example.com               A    <YOUR_TAILSCALE_IP>
   *.homelab.example.com             A    <YOUR_TAILSCALE_IP>
   ```

   Replace `<YOUR_TAILSCALE_IP>` with the value from your `.env` file

5. Enable MagicDNS for your tailnet

6. Test from any device on your Tailscale network:

   ```bash
   ping auth.homelab.example.com
   ```

## Option 2: Local /etc/hosts File (Testing Only)

**Pros:**

- Quick setup for testing
- No external dependencies

**Cons:**

- Must be configured on every device
- Doesn't work on mobile devices easily
- Must be updated manually

**Setup Steps:**

On Linux/macOS:

```bash
sudo nano /etc/hosts
```

On Windows (Run as Administrator):

```
notepad C:\Windows\System32\drivers\etc\hosts
```

Add these lines (replace `<YOUR_TAILSCALE_IP>` with the value from your `.env` file):

```
<YOUR_TAILSCALE_IP> homelab.example.com www.homelab.example.com
<YOUR_TAILSCALE_IP> auth.homelab.example.com
<YOUR_TAILSCALE_IP> grafana.homelab.example.com
<YOUR_TAILSCALE_IP> portainer.homelab.example.com
<YOUR_TAILSCALE_IP> jellyfin.homelab.example.com
<YOUR_TAILSCALE_IP> vault.homelab.example.com
<YOUR_TAILSCALE_IP> cloud.homelab.example.com
<YOUR_TAILSCALE_IP> docs.homelab.example.com
<YOUR_TAILSCALE_IP> n8n.homelab.example.com
<YOUR_TAILSCALE_IP> homeassistant.homelab.example.com
<YOUR_TAILSCALE_IP> uptime.homelab.example.com
<YOUR_TAILSCALE_IP> stremio.homelab.example.com
<YOUR_TAILSCALE_IP> files.homelab.example.com
<YOUR_TAILSCALE_IP> pihole.homelab.example.com
<YOUR_TAILSCALE_IP> prometheus.homelab.example.com
<YOUR_TAILSCALE_IP> netdata.homelab.example.com
<YOUR_TAILSCALE_IP> cadvisor.homelab.example.com
<YOUR_TAILSCALE_IP> alertmanager.homelab.example.com
<YOUR_TAILSCALE_IP> docker.homelab.example.com
```

Save the file and test:

```bash
ping auth.homelab.example.com
```

## Option 3: DuckDNS (External DNS)

**Note:** You already have a DuckDNS token in your `.env` file but it's not configured. This option is NOT recommended for Tailscale-only setups.

**Why not recommended:**

- Exposes your domain to the public internet
- Requires port forwarding (security risk)
- Conflicts with Tailscale-only network design
- Your services are already restricted to Tailscale IPs

## Option 4: Structurally Isolated Public App (Tailscale Funnel)

**Use case:** a public-facing app that must NOT share the operator's Cloudflare account,
tunnel, or domain — so a compromise/suspension of that Cloudflare account can't take the
app down with it. This is distinct from Option 3 above (DuckDNS, rejected for
Tailscale-only *private* services) and distinct from the existing pattern of routing
public apps as subdomains of `lucassantana.tech` via the shared Cloudflare Tunnel (e.g.
CoJam).

**Decision (2026-08-20, via `/debate`, 5 lenses + synthesis):** when the isolation goal is
*structural* (no shared credential/account/blast-radius with the main Cloudflare Tunnel),
use **Tailscale Funnel**, not a second Cloudflare Tunnel on the same account and not free
DDNS.

**Why not the alternatives:**

- **A second Cloudflare Tunnel, same account** (new domain via Porkbun + independent
  `cloudflared` process) — technically clean and cheap (~$9-11/yr), but still shares the
  Cloudflare account, 2FA, and Zero Trust org with the main tunnel. Fine for *namespace*
  isolation (branding, a project that might be spun off/sold), **not** for structural
  isolation.
- **Free DDNS (DuckDNS/FreeDNS/No-IP)** — same objection as Option 3: requires exposing
  a port directly (or CNAME-ing to a tunnel, which re-adds the Cloudflare dependency
  anyway), and silently breaks in 12-24 months (expired token, rotated IP, no SLA).
- **ngrok/Pinggy/LocalXpose free tier** — rotating URL on the free tier; fine for a
  session-length demo, not for anything that needs to stay up.
- **is-a.dev** — legitimate, Cloudflare-sponsored, but manual PR approval (hours-days)
  and no SLA; use only for a personal/OSS showcase, not production.

**Setup:** Funnel is already enabled and in production on this tailnet — Stremio Web is
served through it (see `docs/` + `STREMIO_PUBLIC_URL` in `.env`, PR #26), so there is no
tailnet-level enablement step left to do. To expose an additional app:

```bash
sudo tailscale funnel --bg --https=443 http://127.0.0.1:<local-port>
```

Public URL is `https://<hostname>.<tailnet>.ts.net` — no domain to buy or renew, no
Cloudflare Tunnel config. Note that one Funnel node serves one `:443` target; exposing a
second app on the same host means either a different Funnel port (`--https=8443`) or
path-based routing behind a local reverse proxy.

**Trade-off accepted:** the public hostname carries the tailnet name (`*.ts.net`), no
custom branding. If custom branding is needed later without giving up structural
isolation, CNAME a purchased domain to the Funnel hostname — but that reintroduces an
external domain dependency (just not a Cloudflare-account dependency).

## Verification

After configuring DNS, verify each service:

```bash
# Test DNS resolution
nslookup auth.homelab.example.com

# Test Authentik access (should get HTTP 301 or show login page)
curl -I http://auth.homelab.example.com

# Test HTTPS (should work with valid SSL cert)
curl -I https://auth.homelab.example.com
```

## Troubleshooting

### DNS resolution fails

1. Check Tailscale is running: `tailscale status`
2. Verify Tailscale IP matches: `ip addr show tailscale0`
3. Clear DNS cache:
   - Linux: `sudo systemd-resolve --flush-caches`
   - macOS: `sudo dscacheutil -flushcache`
   - Windows: `ipconfig /flushdns`

### Connection refused after DNS works

> **Note (PR #34):** nginx-proxy was retired. The active reverse proxy is `caddy-lan` (host network). Troubleshooting commands below target it.

1. Verify caddy is running: `docker ps --filter name=caddy-lan`
2. Validate the Caddyfile: `docker exec caddy-lan caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile`
3. Review caddy logs: `docker logs caddy-lan --tail 50`
4. Confirm k3s Traefik is reachable from the host: `curl -H "Host: authentik.k3s.local" http://10.43.242.180/`

### SSL certificate errors

The stack should serve a trusted wildcard cert for `*.homelab.example.com`.
If you see `NET::ERR_CERT_AUTHORITY_INVALID`:

1. Check what certificate is currently served:

   ```bash
   cd /home/luk-server/homelab
   make ssl-status
   ```

2. *(Legacy, nginx-proxy retired)* Cert files were managed by nginx-proxy via `/etc/nginx/ssl/live/`. With caddy-lan + cloudflared, public-facing TLS is terminated at Cloudflare edge; no local cert to inspect. For tailnet HTTPS, use `tailscale cert` (see `docs/tailscale-features-checklist.md`).

4. Re-issue/renew wildcard cert with DNS-01 (Cloudflare token required):

   ```bash
   cd /home/luk-server/homelab
   make ssl-renew
   ```

5. Validate DNS intent:
   - **Tailscale-only access**: hostname can resolve to your Tailscale IP.
   - **Public access via Cloudflare Tunnel**: hostname must resolve through Cloudflare/tunnel, not directly to your Tailscale IP.

## Recommended Setup

For your Tailscale-only homelab:

1. **Use Tailscale MagicDNS** as the primary DNS solution
2. Keep a copy of `/etc/hosts` entries as backup for testing
3. Do NOT use DuckDNS for production (security risk)
4. Document any custom DNS entries in this file

## Current Configuration

- **Tailscale IP:** See `TAILSCALE_IP` in `.env` file
- **Domain:** `homelab.example.com` (see `DOMAIN` in `.env` file)
- **SSL Cert:** Wildcard certificate for `*.homelab.example.com`
- **Network:** All services bound to Tailscale IP only (not publicly accessible)
