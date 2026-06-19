# Updates Audit

> **Historical snapshot (2026-04-14)** — This is part of the homelab audit series. Refer to the audit README for current status and follow-up PRs.

## Python outdated
Package            Version         Latest          Type
------------------ --------------- --------------- -----
anyio              4.11.0          4.13.0          wheel
astroid            3.3.11          4.1.2           wheel
Authlib            1.6.4           1.6.10          wheel
babel              2.17.0          2.18.0          wheel
bandit             1.8.6           1.9.4           wheel
black              25.9.0          26.3.1          wheel
certifi            2025.8.3        2026.2.25       wheel
cfgv               3.4.0           3.5.0           wheel
charset-normalizer 3.4.3           3.4.7           wheel
click              8.3.0           8.3.2           wheel
coverage           7.10.7          7.13.5          wheel
cryptography       46.0.1          46.0.7          wheel
dill               0.4.0           0.4.1           wheel
docutils           0.21.2          0.22.4          wheel
filelock           3.19.1          3.28.0          wheel
identify           2.6.14          2.6.18          wheel
idna               3.10            3.11            wheel
imagesize          1.4.1           2.0.0           wheel
iniconfig          2.1.0           2.3.0           wheel
isort              6.0.1           8.0.1           wheel
joblib             1.5.2           1.5.3           wheel
line_profiler      5.0.0           5.0.2           wheel
mando              0.7.1           0.8.2           wheel
marshmallow        4.0.1           4.3.0           wheel
mypy               1.18.2          1.20.1          wheel
nltk               3.9.1           3.9.4           wheel
nodeenv            1.9.1           1.10.0          wheel
packaging          25.0            26.1            wheel

## Images running (tag scan)
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

## Compose images referenced
    image: ${IMG_ALERTMANAGER:-prom/alertmanager:latest}
    image: ${IMG_AUTHENTIK_SERVER:-ghcr.io/goauthentik/server:latest}
    image: ${IMG_CADVISOR:-gcr.io/cadvisor/cadvisor:latest}
    image: ${IMG_CLOUDFLARED:-cloudflare/cloudflared:latest}
    image: ${IMG_GRAFANA:-grafana/grafana-oss:latest}
    image: ${IMG_HOMEASSISTANT:-ghcr.io/home-assistant/home-assistant:stable}
    image: ${IMG_MARIADB:-mariadb:latest}
    image: ${IMG_N8N:-n8nio/n8n:latest}
    image: ${IMG_NEXTCLOUD:-nextcloud:latest}
    image: ${IMG_NGINX:-nginx:alpine}
    image: ${IMG_PIHOLE:-pihole/pihole:latest}
    image: ${IMG_PORTAINER:-portainer/portainer-ce:latest}
    image: ${IMG_POSTGRES_15_ALPINE:-postgres:15-alpine}
    image: ${IMG_PROMETHEUS:-prom/prometheus:latest}
    image: ${IMG_REDIS_ALPINE:-redis:alpine}
    image: ${IMG_VAULTWARDEN:-vaultwarden/server:latest}
    image: caddy:2-alpine
    image: filebrowser/filebrowser:latest
    image: fmartinou/whats-up-docker:latest
    image: ghcr.io/gethomepage/homepage:latest
    image: ghcr.io/ibm/mcp-context-forge:1.0.0-BETA-2
    image: grafana/loki:latest
    image: grafana/promtail:latest
    image: jellyfin/jellyfin:latest
    image: louislam/uptime-kuma:1
    image: netdata/netdata:latest
    image: paperless-ngx:custom
    image: prom/blackbox-exporter:latest
    image: prom/node-exporter:latest
    image: python:3-alpine

## Helm chart versions
k8s/helm/alertmanager/Chart.yaml:version: 0.1.0
k8s/helm/alertmanager/Chart.yaml:appVersion: "latest"
k8s/helm/authentik/Chart.yaml:version: 0.1.0
k8s/helm/authentik/Chart.yaml:appVersion: "2025.2.4"
k8s/helm/blackbox-exporter/Chart.yaml:version: 0.1.0
k8s/helm/blackbox-exporter/Chart.yaml:appVersion: "latest"
k8s/helm/filebrowser/Chart.yaml:version: 0.1.0
k8s/helm/filebrowser/Chart.yaml:appVersion: "latest"
k8s/helm/grafana/Chart.yaml:version: 0.1.0
k8s/helm/grafana/Chart.yaml:appVersion: "latest"
k8s/helm/homeassistant/Chart.yaml:version: 0.1.0
k8s/helm/homeassistant/Chart.yaml:appVersion: "stable"
k8s/helm/homepage/Chart.yaml:version: 0.1.0
k8s/helm/homepage/Chart.yaml:appVersion: "latest"
k8s/helm/jellyfin/Chart.yaml:version: 0.1.0
k8s/helm/jellyfin/Chart.yaml:appVersion: "latest"
k8s/helm/loki/Chart.yaml:version: 0.1.0
k8s/helm/loki/Chart.yaml:appVersion: "latest"
k8s/helm/n8n/Chart.yaml:version: 0.1.0
k8s/helm/n8n/Chart.yaml:appVersion: "latest"
k8s/helm/nextcloud/Chart.yaml:version: 0.1.0
k8s/helm/nextcloud/Chart.yaml:appVersion: "latest"
k8s/helm/paperless/Chart.yaml:version: 0.1.0
k8s/helm/paperless/Chart.yaml:appVersion: "latest"
k8s/helm/pihole/Chart.yaml:version: 0.1.0
k8s/helm/pihole/Chart.yaml:appVersion: "latest"
k8s/helm/prometheus/Chart.yaml:version: 0.1.0
k8s/helm/prometheus/Chart.yaml:appVersion: "latest"
k8s/helm/promtail/Chart.yaml:version: 0.1.0
k8s/helm/promtail/Chart.yaml:appVersion: "latest"

## GH Actions uses:
  statuses: read
      uses: actions/cache@v4
        uses: actions/checkout@692973e3d937129bcbf40652eb9f2f61becf3332
        uses: actions/checkout@v4
    - uses: actions/checkout@v4
      uses: actions/setup-python@v5
      uses: aquasecurity/trivy-action@master
      uses: codecov/codecov-action@v4
      uses: docker/setup-buildx-action@v3
      uses: github/codeql-action/upload-sarif@v3
      uses: hashicorp/setup-terraform@v3
      uses: pre-commit/action@v3.0.1

## Apt upgradable
Listing...
gh/unknown 2.89.0 amd64 [upgradable from: 2.88.1]
nodejs/nodistro 22.22.2-1nodesource1 amd64 [upgradable from: 22.22.1-1nodesource1]

## Reboot required
no

## Renovate/Dependabot config
NONE — recommend adding renovate.json
