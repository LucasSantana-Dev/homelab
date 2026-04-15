# Security Audit

## UFW rules
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
3389/tcp                   ALLOW       Anywhere
45000:60000/udp            ALLOW       Anywhere                   # Lucky Discord voice UDP
3000/tcp                   ALLOW       192.168.0.0/24             # LAN: open-webui
3333/tcp                   ALLOW       192.168.0.0/24             # LAN: craftvaria-admin
5000/tcp                   ALLOW       192.168.0.0/24             # LAN: docker-registry
8090/tcp                   ALLOW       192.168.0.0/24             # LAN: lucky-nginx
25565/tcp                  ALLOW       192.168.0.0/24             # LAN: minecraft-java
24454/udp                  ALLOW       192.168.0.0/24             # LAN: minecraft-voicechat
5353/udp                   ALLOW       192.168.0.0/24             # LAN: mDNS (avahi)
53/udp                     ALLOW       192.168.0.0/24             # LAN: pihole DNS
53/tcp                     ALLOW       192.168.0.0/24             # LAN: pihole DNS
80/tcp                     ALLOW       192.168.0.0/24             # LAN: nginx/caddy http
443/tcp                    ALLOW       192.168.0.0/24             # LAN: nginx/caddy https
8054/tcp                   ALLOW       192.168.0.0/24             # LAN: pihole admin
22/tcp (v6)                ALLOW       Anywhere (v6)
3389/tcp (v6)              ALLOW       Anywhere (v6)
45000:60000/udp (v6)       ALLOW       Anywhere (v6)              # Lucky Discord voice UDP


## Listening ports
0.0.0.0:22 users:(("sshd",pid=1758,fd=3),("systemd",pid=1,fd=184))
0.0.0.0:25565 users:(("docker-proxy",pid=2966429,fd=8))
0.0.0.0:3000 users:(("docker-proxy",pid=3430,fd=8))
0.0.0.0:3333 users:(("docker-proxy",pid=3413,fd=8))
0.0.0.0:4096 users:(("opencode",pid=1770,fd=18))
0.0.0.0:5000 users:(("docker-proxy",pid=3457,fd=8))
0.0.0.0:53 users:(("docker-proxy",pid=3586178,fd=8))
0.0.0.0:8054 users:(("docker-proxy",pid=3586205,fd=8))
0.0.0.0:8090 users:(("docker-proxy",pid=3528895,fd=8))
100.95.204.103:56358 users:(("tailscaled",pid=1552,fd=20))
*:10250 users:(("k3s-server",pid=10912,fd=192))
127.0.0.1:10010 users:(("containerd",pid=10986,fd=135))
127.0.0.1:10248 users:(("k3s-server",pid=10912,fd=194))
127.0.0.1:10249 users:(("k3s-server",pid=10912,fd=199))
127.0.0.1:10256 users:(("k3s-server",pid=10912,fd=196))
127.0.0.1:10257 users:(("k3s-server",pid=10912,fd=158))
127.0.0.1:10258 users:(("k3s-server",pid=10912,fd=203))
127.0.0.1:10259 users:(("k3s-server",pid=10912,fd=167))
127.0.0.1:2019 users:(("caddy",pid=3600549,fd=4))
127.0.0.1:6444 users:(("k3s-server",pid=10912,fd=18))
[::]:22 users:(("sshd",pid=1758,fd=4),("systemd",pid=1,fd=186))
[::]:25565 users:(("docker-proxy",pid=2966436,fd=8))
[::]:3000 users:(("docker-proxy",pid=3437,fd=8))
[::]:5000 users:(("docker-proxy",pid=3464,fd=8))
*:6443 users:(("k3s-server",pid=10912,fd=12))
[::]:8090 users:(("docker-proxy",pid=3528904,fd=8))
*:80 users:(("caddy",pid=3600549,fd=7))
*:9090 users:(("systemd",pid=1,fd=161))
[fd7a:115c:a1e0::dc01:cc69]:62107 users:(("tailscaled",pid=1552,fd=21))

## Bandit summary (HIGH/MEDIUM)

## pip safety check
   ignore command-line argument or add the ignore to your safety policy file.


[31m-> Vulnerability found in authlib version 1.6.4[0m
[1m   Vulnerability ID: [0m84339
[1m   Affected spec: [0m>=1.0.0,<=1.6.5
[1m   ADVISORY: [0mAffected versions of the Authlib package are vulnerable
   to Cross-Site Request Forgery (CSRF) due to cache-backed OAuth state...
[1m   CVE-2025-68158[0m
[1m   For more information about this vulnerability, visit
   [0mhttps://getsafety.com/v/84339/97c[0m
   To ignore this vulnerability, use PyUp vulnerability id 84339 in safety’s
   ignore command-line argument or add the ignore to your safety policy file.


+==============================================================================+
   [32m[1mREMEDIATIONS[0m

  17 vulnerabilities were reported in 11 packages. For detailed remediation &
  fix recommendations, upgrade to a commercial license.

+==============================================================================+

 Scan was completed. 17 vulnerabilities were reported.

+==============================================================================+[0m


[33m[1m+===========================================================================================================================================================================================+[0m


[31m[1mDEPRECATED: [0m[33m[1mthis command (`check`) has been DEPRECATED, and will be unsupported beyond 01 June 2024.[0m


[32mWe highly encourage switching to the new [0m[32m[1m`scan`[0m[32m command which is easier to use, more powerful, and can be set up to mimic the deprecated command if required.[0m


[33m[1m+===========================================================================================================================================================================================+[0m



## .env keys (classified, values never printed)
      1 SENSITIVE WUD_AUTH_PASSWORD
      1 SENSITIVE VAULTWARDEN_ADMIN_TOKEN
      1 SENSITIVE SENTRY_AUTH_TOKEN
      1 SENSITIVE PIHOLE_WEB_PASSWORD
      1 SENSITIVE PAPERLESS_SECRET_KEY
      1 SENSITIVE PAPERLESS_DB_PASSWORD
      1 SENSITIVE PAPERLESS_ADMIN_PASSWORD
      1 SENSITIVE NEXTCLOUD_DB_ROOT_PASSWORD
      1 SENSITIVE NEXTCLOUD_DB_PASSWORD
      1 SENSITIVE N8N_PASSWORD
      1 SENSITIVE HOMEASSISTANT_KEY
      1 SENSITIVE GRAFANA_PASSWORD
      1 SENSITIVE GITHUB_TOKEN
      1 SENSITIVE DOCKER_HUB_TOKEN
      1 SENSITIVE CLOUDFLARE_API_TOKEN
      1 SENSITIVE CF_TUNNEL_TOKEN
      1 SENSITIVE AUTHENTIK_SECRET_KEY
      1 SENSITIVE AUTHENTIK_PORTAINER_CLIENT_SECRET
      1 SENSITIVE AUTHENTIK_GRAFANA_CLIENT_SECRET
      1 SENSITIVE AUTHENTIK_DB_PASSWORD
      1 plain WUD_SMTP_USER
      1 plain WUD_SMTP_PORT
      1 plain WUD_SMTP_PASS
      1 plain WUD_PORT
      1 plain WUD_DISCORD_WEBHOOK_URL
      1 plain WUD_AUTH_USER
      1 plain WATCHDOG_RECOVERY_WINDOW_MINUTES
      1 plain WATCHDOG_REBOOT_ENABLED
      1 plain WATCHDOG_DISCORD_WEBHOOK
      1 plain UPTIME_KUMA_PORT
      1 plain UPDATE_DISCORD_WEBHOOK_URL
      1 plain TIMEZONE
      1 plain TAILSCALE_IP
      1 plain PUID
      1 plain PROMETHEUS_PORT
      1 plain PORTAINER_PORT
      1 plain PIHOLE_WEB_PORT
      1 plain PIHOLE_DNS_PORT
      1 plain PGID
      1 plain NODE_EXPORTER_PORT
      1 plain N8N_USER
      1 plain IMG_VAULTWARDEN
      1 plain IMG_REDIS_ALPINE
      1 plain IMG_PROMETHEUS
      1 plain IMG_POSTGRES_15_ALPINE
      1 plain IMG_PORTAINER
      1 plain IMG_PIHOLE
      1 plain IMG_PAPERLESS_BASE
      1 plain IMG_NGINX
      1 plain IMG_NEXTCLOUD
      1 plain IMG_N8N
      1 plain IMG_MARIADB
      1 plain IMG_HOMEASSISTANT
      1 plain IMG_GRAFANA
      1 plain IMG_CLOUDFLARED
      1 plain IMG_CADVISOR
      1 plain IMG_AUTHENTIK_SERVER
      1 plain IMG_ALERTMANAGER
      1 plain HOMEPAGE_PORT
      1 plain HOMEASSISTANT_PORT
      1 plain GRAFANA_PORT
      1 plain GRAFANA_OAUTH_ENABLED
      1 plain GRAFANA_DISABLE_LOGIN_FORM
      1 plain FILEBROWSER_PORT
      1 plain DOMAIN
      1 plain CERTBOT_EMAIL
      1 plain BIND_IP
      1 plain AUTHENTIK_SESSION_DAYS
      1 plain AUTHENTIK_REQUIRE_MFA
      1 plain AUTHENTIK_PORTAINER_CLIENT_ID
      1 plain AUTHENTIK_GRAFANA_CLIENT_ID
      1 plain AUTHENTIK_ALLOWED_GITHUB_USERNAME
      1 plain AUTHENTIK_ALLOWED_EMAIL
      1 plain ALERTMANAGER_DISCORD_WEBHOOK
      1 EMPTY-STUB WUD_SMTP_HOST
      1 EMPTY-STUB NETDATA_CLAIM_TOKEN
      1 EMPTY-STUB FORGE_MCP_JWT_SECRET_KEY

## Running container image digests (pin coverage)
789528aa0082
caddy:2-alpine
cloudflare/cloudflared:latest
craftvaria-admin-backend
craftvaria-admin-frontend
ghcr.io/lucassantana-dev/lucky-backend:latest
ghcr.io/lucassantana-dev/lucky-frontend:latest
ghcr.io/lucassantana-dev/lucky-nginx:latest
ghcr.io/playit-cloud/playit-agent:latest
itzg/minecraft-server:java21
lucky-webhook
openwebui/open-webui:latest
pihole/pihole:latest
postgres:18-alpine
python:3-alpine
redis:8-alpine
registry:2
