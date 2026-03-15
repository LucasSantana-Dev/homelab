# Homelab Monitoring Stack

Operate and troubleshoot the Prometheus/Grafana/Loki/Alertmanager monitoring stack.

## When to Use
- Validating Prometheus or Alertmanager config before applying
- Querying Loki logs for a service
- Diagnosing missing metrics, broken alerts, or false positives
- Checking watchdog and burn-in health status
- Tracing the Discord alert notification chain

## Stack Components

| Container | Role | Port |
|---|---|---|
| `prometheus` | Metrics collection and storage | 9091 (Tailscale + localhost) |
| `grafana` | Dashboards and visualization | 3002 (Tailscale only) |
| `loki` | Log aggregation | 3100 (Tailscale + localhost) |
| `promtail` | Log shipping to Loki | — (no exposed port) |
| `alertmanager` | Alert routing and Discord notifications | 9093 (localhost + Tailscale) |
| `node-exporter` | Host system metrics | 9100 (localhost only) |
| `cadvisor` | Container metrics | 8082 (localhost only) |
| `blackbox-exporter` | HTTP/TCP endpoint probes | 9115 (localhost only) |
| `netdata` | Real-time system monitoring | 19999 (Tailscale only) |

## Prometheus

### Config validation
```bash
docker exec prometheus promtool check config /etc/prometheus/prometheus.yml
```

### Reload config without restart (after editing)
```bash
curl -s -X POST http://localhost:9091/-/reload
```

### Check alert rules
```bash
docker exec prometheus promtool check rules /etc/prometheus/alerts.yml
```

### Config files
- `config/prometheus/prometheus.yml` — scrape configs and remote-write rules
- `config/prometheus/alerts.yml` — alerting rules

### Verify targets are up
```bash
curl -s http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastError: .lastError}'
```

## Alertmanager

### Config validation
```bash
docker exec alertmanager amtool check-config /etc/alertmanager/alertmanager.yml
```

### Config file
- `config/alertmanager/alertmanager.yml` — routing tree and receiver definitions

### View active alerts
```bash
curl -s http://localhost:9093/api/v2/alerts | jq '.[] | {name: .labels.alertname, status: .status.state}'
```

### Silence an alert (e.g. during maintenance)
```bash
docker exec alertmanager amtool --alertmanager.url=http://localhost:9093 silence add alertname="<AlertName>" --duration=2h --comment="maintenance"
```

## Grafana

Grafana binds to the Tailscale IP only. Access via `https://grafana.<DOMAIN>`.

- Auth: Authentik OAuth (primary), admin password fallback (see `.env` `GRAFANA_PASSWORD`)
- Data sources: Prometheus (`http://prometheus:9090`) and Loki (`http://loki:3100`)
- Persistent data: `grafana_data` named volume

### Check Grafana is healthy
```bash
curl -s http://${TAILSCALE_IP}:3002/api/health | jq .
```

## Loki

### Query logs via LogQL (CLI)
```bash
# Last 100 lines from a container
docker exec loki logcli query '{container="<name>"}' --limit=100 --addr=http://localhost:3100

# Filter for errors in the last hour
docker exec loki logcli query '{container="<name>"} |= "error"' --since=1h --addr=http://localhost:3100
```

### Config file
- `config/loki/loki-config.yaml`

### Loki healthcheck note
Loki has `healthcheck: disable: true` in `compose/monitoring.yml`. A missing healthcheck in `docker ps` is expected — it does not indicate a problem. Verify Loki is receiving logs by querying it directly.

### Check promtail is shipping logs
```bash
docker logs --tail 50 promtail
curl -s http://localhost:3100/metrics | grep loki_distributor_bytes_received_total
```

## Watchdog Timer

The watchdog runs as a systemd service that fires every minute to check container and host health.

```bash
# Check timer status and next trigger
systemctl status homelab-watchdog.timer --no-pager

# Check last run output
journalctl -u homelab-watchdog.service --no-pager -n 50

# Manually trigger a watchdog check
systemctl start homelab-watchdog.service
```

Watchdog script: `scripts/maintenance/homelab-watchdog.sh`

The watchdog detects: degraded containers, swap pressure, OOM events, and performs recovery actions (container restarts). Failures are counted in the burn-in status report.

## Burn-in Status

```bash
# Full window (default 24 hours)
bash scripts/maintenance/burnin-status.sh

# Custom window
bash scripts/maintenance/burnin-status.sh --since "12 hours ago"
bash scripts/maintenance/burnin-status.sh --since "48 hours ago"
```

**Interpreting output:**
- **Overall PASS**: no watchdog failures in the window
- **Overall FAIL**: check `Watchdog service failures` count; transient timeouts during swap spikes are common
- **Zero degraded + zero recovery = structurally healthy** even if FAIL due to old timeout entries
- **cAdvisor OOM events**: expected occasionally; cadvisor has a 768M limit and is the most frequent OOM victim

## Discord Alerting Chain

```
Prometheus evaluates rules (config/prometheus/alerts.yml)
  → fires to Alertmanager (localhost:9093)
    → Alertmanager routes via alertmanager.yml
      → receiver sends webhook POST to ALERTMANAGER_DISCORD_WEBHOOK
        → Discord channel notification
```

The `ALERTMANAGER_DISCORD_WEBHOOK` env var is passed into the `alertmanager` container. Verify it is set:
```bash
grep ALERTMANAGER_DISCORD_WEBHOOK /home/luk-server/homelab/.env
```

Test the webhook manually:
```bash
curl -s -X POST "$ALERTMANAGER_DISCORD_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{"content": "test alert from homelab"}'
```

## Common Issues

### cAdvisor OOM
- **Symptom**: `cadvisor` exits with code 137, missing container metrics in Grafana
- **Fix**: `docker restart cadvisor` — it comes back cleanly; no data loss
- **Root cause**: cAdvisor is memory-hungry under high container churn; limit is 768M with 1536M swap

### Loki healthcheck false positive
- **Symptom**: `docker ps` shows no healthcheck for loki (or "(unhealthy)" if misconfigured)
- **Diagnosis**: `healthcheck: disable: true` is intentional; check actual log ingestion instead
- **Fix**: query Loki directly or check promtail logs

### False positive alerts (swap spikes)
- During Minecraft GC or large n8n runs, swap pressure briefly triggers watchdog
- If the alert auto-resolves within 5 minutes and burn-in shows clean recent window, treat as transient
- Silence the alert with `amtool` if doing planned maintenance

### Prometheus scrape gaps
- **Symptom**: gaps in Grafana time series
- **Check**: `docker logs --tail 50 prometheus` for scrape errors
- **Common cause**: target container restarted and changed IP; reload Prometheus config after container recreation

### Alertmanager not firing to Discord
1. Check `ALERTMANAGER_DISCORD_WEBHOOK` is set in `.env` and passed to container
2. Validate config: `docker exec alertmanager amtool check-config /etc/alertmanager/alertmanager.yml`
3. Check active alerts: `curl -s http://localhost:9093/api/v2/alerts | jq .`
4. Check alertmanager logs: `docker logs --tail 50 alertmanager`

## Scripts Reference
- `scripts/maintenance/burnin-status.sh` — burn-in health summary
- `scripts/maintenance/homelab-watchdog.sh` — per-minute health check (systemd)
- `scripts/maintenance/capture-pressure-snapshot.sh` — labeled pressure snapshot
- `scripts/maintenance/pressure-watch.sh` — long-running pressure monitor
