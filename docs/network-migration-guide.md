# Network Segmentation Migration Guide

## Overview

This guide documents the migration of 27 services from a single default bridge network to a segmented network architecture with four isolated networks. This migration is **deferred to a maintenance window** due to the risk of service disruption.

## Network Architecture

### Network Definitions

| Network | Subnet | Type | Purpose |
|---------|--------|------|---------|
| `frontend` | 172.20.0.0/24 | Bridge | User-facing services, reverse proxy routing |
| `backend` | 172.21.0.0/24 | Bridge (internal) | Processing services, no internet access |
| `monitoring` | 172.22.0.0/24 | Bridge | Observability stack, metrics collection |
| `database` | 172.23.0.0/24 | Bridge (internal) | Database services, no internet access |

### Security Benefits

- **Database Isolation**: Database networks are internal-only (no internet access)
- **Service Segmentation**: Clear separation between frontend, backend, and monitoring tiers
- **Attack Surface Reduction**: Compromised frontend services cannot directly access databases
- **Network Policies**: Easy to implement fine-grained firewall rules per network

## Service-to-Network Mapping

### Frontend Network (172.20.0.0/24)
User-facing services accessible via Nginx reverse proxy:
- `nginx` (also monitoring) - Routes to all services, Prometheus metrics
- `homepage` - Dashboard
- `homeassistant` - Home automation
- `stremio` - Media server
- `vaultwarden` - Password manager
- `jellyfin` - Media server
- `n8n` - Workflow automation
- `nextcloud` - Cloud storage
- `pihole` - DNS/Ad blocker
- `filebrowser` - File manager

### Monitoring Network (172.22.0.0/24)
Observability and monitoring services:
- `prometheus` (also frontend, database) - Metrics collection, scrapes all services
- `grafana` (also frontend) - Dashboards, user access via frontend
- `alertmanager` - Alert routing
- `blackbox-exporter` - Endpoint probing
- `loki` - Log aggregation
- `promtail` (also backend) - Log collection
- `node-exporter` - Host metrics
- `cadvisor` - Container metrics
- `netdata` - Real-time monitoring
- `uptime-kuma` (also frontend) - Status page
- `whats-up-docker` (also frontend) - Container updates
- `portainer` (also frontend) - Container management

### Backend Network (172.21.0.0/24, Internal)
Processing services without internet access:
- `promtail` (also monitoring) - Log collection only

### Database Network (172.23.0.0/24, Internal)
Database services without internet access:
- `nextcloud-db` - MariaDB for Nextcloud
- `nextcloud-redis` - Redis cache for Nextcloud
- `prometheus` (also frontend, monitoring) - Scrapes database metrics
- `nextcloud` (also frontend) - Needs database access

## Pre-Migration Checklist

- [ ] **Backup current state**
  ```bash
  cd /home/luk-server/homelab
  ./scripts/backup-automation.sh  # If available
  # OR manual backup:
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  tar -czf backups/homelab_pre-network-migration_$TIMESTAMP.tar.gz \
    --exclude='./backups' --exclude='./venv' --exclude='./logs' \
    --exclude='./appdata/nextcloud/db' --exclude='./.git' \
    ./config ./appdata ./docker-compose.yml .env
  ```

- [ ] **Verify all services healthy**
  ```bash
  docker ps --filter "health=healthy" | wc -l
  docker ps --format "table {{.Names}}\t{{.Status}}" | grep -i unhealthy
  ```

- [ ] **Schedule maintenance window**
  - Estimated duration: 30-60 minutes
  - Plan for potential rollback time: +30 minutes
  - Notify users of downtime window

- [ ] **Review current network state**
  ```bash
  docker network ls
  docker compose config | grep -A 2 "networks:"
  ```

## Migration Steps

### Step 1: Frontend Services (Low Risk)

Update `docker-compose.yml` for frontend services:

```yaml
# Nginx - Routes to all services
nginx:
  networks:
    - frontend
    - monitoring  # For Prometheus metrics

# User-facing services
homepage:
  networks:
    - frontend

homeassistant:
  networks:
    - frontend

stremio:
  networks:
    - frontend

vaultwarden:
  networks:
    - frontend

jellyfin:
  networks:
    - frontend

n8n:
  networks:
    - frontend

pihole:
  networks:
    - frontend

filebrowser:
  networks:
    - frontend
```

**Deploy frontend services:**
```bash
docker compose up -d --no-deps nginx homepage homeassistant stremio vaultwarden jellyfin n8n pihole filebrowser
```

**Validation:**
```bash
# Check services are up
docker ps | grep -E 'nginx|homepage|homeassistant|stremio|vaultwarden|jellyfin|n8n|pihole|filebrowser'

# Test access via homepage
curl -I https://homelab.example.com
```

### Step 2: Monitoring Services (Medium Risk)

Update `docker-compose.yml` for monitoring services:

```yaml
# Prometheus - Scrapes all services
prometheus:
  networks:
    - monitoring
    - frontend  # Scrape frontend services
    - database  # Scrape database metrics

# Grafana - User access + monitoring
grafana:
  networks:
    - frontend  # User access
    - monitoring  # Prometheus connection

# Monitoring-only services
alertmanager:
  networks:
    - monitoring

blackbox-exporter:
  networks:
    - monitoring

loki:
  networks:
    - monitoring

node-exporter:
  networks:
    - monitoring

cadvisor:
  networks:
    - monitoring

netdata:
  networks:
    - monitoring

# Multi-network monitoring services
uptime-kuma:
  networks:
    - frontend  # User access
    - monitoring  # Monitor other services

whats-up-docker:
  networks:
    - frontend  # User access
    - monitoring  # Monitor containers

portainer:
  networks:
    - frontend  # User access
    - monitoring  # Manage containers
```

**Deploy monitoring services:**
```bash
docker compose up -d --no-deps prometheus grafana alertmanager blackbox-exporter loki node-exporter cadvisor netdata uptime-kuma whats-up-docker portainer
```

**Validation:**
```bash
# Check Prometheus targets
curl -s http://localhost:9091/api/v1/targets | jq '.data.activeTargets | length'

# Verify Grafana can reach Prometheus
docker logs grafana 2>&1 | grep -i "prometheus" | tail -5
```

### Step 3: Backend & Database Services (High Risk)

Update `docker-compose.yml` for backend and database services:

```yaml
# Promtail - Log collection
promtail:
  networks:
    - backend  # Collect logs
    - monitoring  # Send to Loki

# Nextcloud stack
nextcloud:
  networks:
    - frontend  # User access
    - database  # Database connection

nextcloud-db:
  networks:
    - database

nextcloud-redis:
  networks:
    - database
```

**Deploy backend/database services:**
```bash
docker compose up -d --no-deps promtail nextcloud nextcloud-db nextcloud-redis
```

**Validation:**
```bash
# Verify database connectivity
docker exec nextcloud-db mariadb-admin ping -h localhost

# Test Nextcloud access
curl -I https://cloud.homelab.example.com
```

### Step 4: Final Validation

**Health Checks:**
```bash
# All services should be healthy
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -v "Up.*healthy"

# Check for any exited/crashed containers
docker ps -a --filter "status=exited"
```

**Connectivity Tests:**
```bash
# Test Prometheus scraping
curl -s http://localhost:9091/api/v1/targets | \
  jq '.data.activeTargets[] | select(.health != "up") | {job: .labels.job, health: .health}'

# Test Grafana access to datasources
docker logs grafana 2>&1 | grep -i "error" | tail -10

# Test user access via homepage
curl -s https://homelab.example.com | grep -q "Homepage" && echo "✅ Homepage accessible"
```

**Service Connectivity Matrix:**
- [ ] Homepage → All frontend services
- [ ] Nginx → All proxied services
- [ ] Prometheus → All scrape targets
- [ ] Grafana → Prometheus, Loki
- [ ] Nextcloud → nextcloud-db, nextcloud-redis
- [ ] Promtail → Loki

## Rollback Procedure

If issues occur during migration, rollback to default network:

```bash
# Stop all services
docker compose down

# Revert docker-compose.yml changes
git checkout HEAD -- docker-compose.yml

# Restart all services on default network
docker compose up -d

# Verify services are accessible
docker ps --filter "health=healthy"
```

## Post-Migration

### Monitor for Issues

Monitor logs for 24-48 hours after migration:

```bash
# Check for connection errors
docker logs --since 1h nginx 2>&1 | grep -i "error"
docker logs --since 1h prometheus 2>&1 | grep -i "error"
docker logs --since 1h grafana 2>&1 | grep -i "error"

# Monitor Prometheus targets
# Visit: https://prometheus.homelab.example.com/targets
```

### Update Documentation

- [ ] Update CHANGELOG.md with migration date and results
- [ ] Document any issues encountered and resolutions
- [ ] Update network architecture diagram (if exists)

## Troubleshooting

### Service Cannot Connect to Another Service

**Symptom**: Service logs show connection refused or timeout errors

**Solution**:
1. Verify both services are on the same network:
   ```bash
   docker inspect <service1> | grep -A 10 "Networks"
   docker inspect <service2> | grep -A 10 "Networks"
   ```
2. Check network connectivity:
   ```bash
   docker exec <service1> ping <service2>
   ```
3. If connectivity fails, add the missing network to docker-compose.yml

### Prometheus Cannot Scrape Targets

**Symptom**: Targets show as "down" in Prometheus UI

**Solution**:
1. Ensure Prometheus is on the same network as the target
2. For frontend services, Prometheus needs `frontend` network
3. For database services, Prometheus needs `database` network

### Nginx Cannot Proxy to Backend Services

**Symptom**: 502 Bad Gateway errors

**Solution**:
1. Verify Nginx is on the `frontend` network
2. Ensure proxied services are also on `frontend` network
3. Check Nginx logs:
   ```bash
   docker logs nginx 2>&1 | grep -i "upstream"
   ```

## Network Isolation Verification

After migration, verify network isolation is working:

```bash
# Database services should NOT have internet access
docker exec nextcloud-db ping -c 1 8.8.8.8  # Should FAIL

# Frontend services should have internet access
docker exec nginx ping -c 1 8.8.8.8  # Should SUCCEED

# Monitoring can access frontend services
docker exec prometheus ping -c 1 nginx  # Should SUCCEED
```

## Expected Outcomes

- **Security**: Database networks isolated from internet
- **Performance**: Reduced broadcast traffic per network
- **Clarity**: Clear service boundaries and dependencies
- **Flexibility**: Easy to add network policies/firewall rules

## Notes

- Migration is **deferred** to maintenance window
- Estimated time: 30-60 minutes
- Risk level: Medium (potential for service disruption)
- Backup mandatory before proceeding
- Rollback procedure tested and documented
