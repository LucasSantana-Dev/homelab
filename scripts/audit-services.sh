#!/usr/bin/env bash
# Run live audit of homelab docker services. Collects resource usage,
# overlap evidence, and age/restart signals so stale services can be
# pruned.
#
# Usage (from laptop):
#   ssh homelab 'bash -s' < scripts/audit-services.sh > docs/audits/$(date +%F)-live.log
#
# Usage (on homelab):
#   bash scripts/audit-services.sh > /tmp/audit.log

set -euo pipefail

section() { printf '\n===%s===\n' "$1"; }

section HOST
uptime
hostname
uname -sr

section MEMORY
free -h

section DISK
df -h / /var/lib/docker 2>/dev/null | head -5

section LOAD
cat /proc/loadavg

section DOCKER_PS
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | head -80

section DOCKER_STATS
docker stats --no-stream \
  --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}' \
  | head -80

section CONTAINER_AGE_AND_RESTARTS
printf '%-28s %-22s %-4s %s\n' NAME STARTED_AT RESTART EXIT
for c in $(docker ps --format '{{.Names}}'); do
  inspect=$(docker inspect --format '{{.State.StartedAt}}|{{.RestartCount}}|{{.State.ExitCode}}' "$c" 2>/dev/null)
  printf '%-28s %s\n' "$c" "$inspect"
done

section STOPPED_CONTAINERS
docker ps -a --filter 'status=exited' --filter 'status=dead' \
  --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' | head -40

section IMAGE_DISK
docker system df

section DANGLING
printf 'dangling_images=%s\n' "$(docker images -f dangling=true -q | wc -l)"
printf 'dangling_volumes=%s\n' "$(docker volume ls -f dangling=true -q | wc -l)"

section CADDY_ACCESS_7D
if docker ps --format '{{.Names}}' | grep -qE '^caddy(-lan)?$'; then
  for name in caddy-lan caddy; do
    docker ps --format '{{.Names}}' | grep -qx "$name" || continue
    docker logs --since 7d "$name" 2>&1 \
      | grep -oE '"host":"[^"]+"' | sort | uniq -c | sort -rn | head -20
    break
  done
else
  echo "(no caddy container running)"
fi

section SYSTEMD_SERVICES
systemctl list-units --type=service --state=running --no-pager | head -40

section LISTENING_PORTS
if command -v ss >/dev/null; then
  sudo ss -ltnp 2>/dev/null | head -40 || ss -ltn | head -40
else
  sudo netstat -ltnp 2>/dev/null | head -40
fi

section JOURNAL_ERRORS_24H
sudo journalctl --since '24 hours ago' -p err --no-pager 2>/dev/null \
  | tail -30 || echo "(journalctl unavailable)"

section DOCKER_COMPOSE_ACTIVE
cd "${HOMELAB_DIR:-$HOME/homelab}" 2>/dev/null \
  && docker compose ps --format 'table {{.Service}}\t{{.Status}}\t{{.State}}' 2>/dev/null \
  || echo "(compose root not found)"
