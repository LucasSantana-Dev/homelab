#!/bin/bash
# Idempotent UFW baseline for the homelab host — LAN-scoped by default.
# Run this as the source of truth instead of ad-hoc `ufw allow` commands.
set -euo pipefail

LAN="${LAN:-192.168.0.0/24}"

sudo ufw --force enable
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH from anywhere (Tailscale + LAN + WAN) — intentional, SSH keys only.
sudo ufw allow 22/tcp comment "SSH"

# Windows RDP — LAN-only (was ALLOW Anywhere; BlueKeep-family CVE surface).
sudo ufw delete allow 3389/tcp 2>/dev/null || true
sudo ufw allow from "$LAN" to any port 3389 proto tcp comment "LAN: RDP"

# Lucky Discord voice — WAN (inbound UDP needed for Discord voice).
sudo ufw allow 45000:60000/udp comment "Lucky Discord voice UDP"

# Docker bridge networks → host port 80 — lets cloudflared (in the
# `homelab_frontend` network, CIDR 172.28.0.0/24) reach the
# host-networked caddy-lan at host.docker.internal:80. Without this,
# the Cloudflare tunnel serves all *.luk-homeserver.com.br hostnames
# with "context canceled" origin errors. Range covers the whole
# RFC1918 172.16.0.0/12 block so all docker project networks work.
sudo ufw allow from 172.16.0.0/12 to any port 80 proto tcp comment "docker → caddy-lan (PR#34 ingress)"

# LAN-scoped services. Edit this list when services change.
while IFS='|' read -r port proto label; do
  [ -z "$port" ] && continue
  sudo ufw allow from "$LAN" to any port "$port" proto "$proto" comment "LAN: $label" || true
done <<'SPECS'
53|tcp|pihole DNS
53|udp|pihole DNS
80|tcp|nginx/caddy http
443|tcp|nginx/caddy https
3000|tcp|open-webui
3333|tcp|craftvaria-admin
5000|tcp|docker-registry
5353|udp|mDNS (avahi)
8054|tcp|pihole admin
8090|tcp|lucky-nginx
24454|udp|minecraft-voicechat
25565|tcp|minecraft-java
SPECS

sudo ufw reload
sudo ufw status verbose
