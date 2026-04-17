# Observability Stack

Production-ready monitoring for homelab: Prometheus + Grafana + Node Exporter + cAdvisor + Blackbox Exporter.

## Components

- **Prometheus**: Time-series database + scraper (15s interval, 30-day retention)
- **Grafana**: Visualization + alerting (3000 with provisioned Prometheus datasource)
- **Node Exporter**: Host metrics (CPU, memory, disk, network)
- **cAdvisor**: Container metrics (memory, CPU, I/O)
- **Blackbox Exporter**: HTTP/TCP health checks for external services

## Architecture

All components run in the `observability` Docker network. Prometheus scrapes:
- Node Exporter (9100)
- cAdvisor (8080)
- Blackbox Exporter (9115)
- Grafana itself (3000)

Targets for health checks:
- Lucky API: `http://lucky-api:5000/api/health`
- Craftvaria RCON: `tcp://craftvaria:25575`
- Pi-hole Admin: `http://pihole:80/admin`

## Starting the Stack

```bash
cd observability/
docker-compose up -d
```

Wait for health checks to pass (30s typical):

```bash
docker-compose ps
```

## Accessing Dashboards

- **Grafana**: http://localhost:3000 (admin / admin — **change password**)
- **Prometheus**: http://localhost:9090 (no auth)
- **cAdvisor**: http://localhost:8080

## Included Dashboards

- **Docker Host Metrics**: CPU and memory usage
- **Container Metrics**: Per-container memory and I/O

Pre-provisioned from JSON in `grafana/provisioning/dashboards/`.

## Reverse Proxy Integration

To expose Grafana via Caddy:

```caddy
grafana.home {
  reverse_proxy localhost:3000
}
```

Add to `/config/caddy/Caddyfile`, then reload Caddy.

## Health Checks

Prometheus scrapes every 15s. Check via:

```bash
curl http://localhost:9090/api/v1/targets
```

Green/Up endpoints are healthy. Red/Down means probe failed.

## Persistence

Data volumes:
- `prometheus_data`: Metrics (30-day rolling)
- `grafana_data`: Dashboards, user preferences, plugins

Located in `observability_prometheus_data` and `observability_grafana_data` Docker volumes.

## Next Steps

1. Change Grafana admin password
2. Configure alerting rules in `prometheus/prometheus.yml`
3. Import or create custom dashboards
4. Set up notification integrations (Discord, Slack, etc.)
5. Add application-specific metrics to Prometheus targets

## References

- Prometheus: https://prometheus.io/docs/
- Grafana: https://grafana.com/docs/
- Node Exporter: https://github.com/prometheus/node_exporter
- cAdvisor: https://github.com/google/cadvisor
- Blackbox Exporter: https://github.com/prometheus/blackbox_exporter
