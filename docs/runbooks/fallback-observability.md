# Fallback Observability — Direct Scrape Queries

When Prometheus or Grafana are unavailable, you can query the underlying metric exporters directly for basic observability.

## Context

Netdata has been retired (ADR-0011); the stack now relies on:
- **node-exporter** for host-level metrics (CPU, memory, disk, network)
- **cadvisor** for per-container metrics (resource usage, process counts)
- **Prometheus** for scraping and retention
- **Grafana** for dashboards

If Prometheus or Grafana are broken, these direct scrape endpoints provide a fallback to diagnose the issue.

## Direct Scrape Endpoints

### Node Exporter (Host Metrics)

**From inside a compose service container:**
```bash
curl http://node-exporter:9100/metrics
```

**From the host (via exposed loopback port):**
```bash
curl http://127.0.0.1:9100/metrics
```

Output: Prometheus text format. Look for:
- `node_cpu_seconds_total` — CPU usage
- `node_memory_MemAvailable_bytes` — available memory
- `node_filesystem_avail_bytes` — disk space per mount
- `node_network_receive_bytes_total` — network I/O

### cAdvisor (Container Metrics)

**From inside a compose service container:**
```bash
curl http://cadvisor:8080/metrics
```

**From the host (via exposed loopback port):**
```bash
curl http://127.0.0.1:8082/metrics
```

Output: Prometheus text format. Look for:
- `container_cpu_usage_seconds_total` — per-container CPU
- `container_memory_usage_bytes` — per-container memory
- `container_network_receive_bytes_total` — per-container network I/O

## Quick Diagnosis

If Prometheus is down but the exporters are up:
1. Verify node-exporter: `curl http://127.0.0.1:9100/metrics | head -20`
2. Verify cadvisor: `curl http://127.0.0.1:8082/metrics | head -20`
3. Check Prometheus logs: `docker logs prometheus`

If exporters are down, verify they are running:
```bash
docker ps | grep -E "node-exporter|cadvisor"
```

## Revisit

If you rely on this fallback more than once per quarter, consider:
- Adding a second Prometheus instance for redundancy
- Alerting on Prometheus/Grafana availability in Healthchecks
- Building a lightweight JSON API that aggregates export metrics
