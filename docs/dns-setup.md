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

1. Access your Tailscale admin console at https://login.tailscale.com/admin/dns

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

1. Verify nginx is running: `docker ps | grep nginx`
2. Check nginx can reach authentik: `docker exec nginx-proxy ping authentik-server`
3. Review nginx logs: `docker logs nginx-proxy`

### SSL certificate errors

Your wildcard cert at `/etc/nginx/ssl/live/homelab.example.com/` covers all subdomains. If you see SSL errors:

1. Verify cert files exist in nginx container:
   ```bash
   docker exec nginx-proxy ls -la /etc/nginx/ssl/live/homelab.example.com/
   ```

2. Check cert expiration:
   ```bash
   docker exec nginx-proxy openssl x509 -in /etc/nginx/ssl/live/homelab.example.com/fullchain.pem -noout -dates
   ```

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
