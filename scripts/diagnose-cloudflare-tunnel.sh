#!/usr/bin/env bash
# Diagnose Cloudflare Tunnel (cloudflared) issues, especially Error 1033.
# Safe to run repeatedly — read-only.
#
# Usage (from laptop):
#   ssh homelab 'bash -s' < scripts/diagnose-cloudflare-tunnel.sh
#
# Usage (on homelab):
#   bash scripts/diagnose-cloudflare-tunnel.sh

set -euo pipefail

section() { printf '\n=== %s ===\n' "$1"; }

section HOST_TIME
date -u +'%Y-%m-%dT%H:%M:%SZ'

section CONTAINER_STATE
if docker ps -a --format '{{.Names}}' | grep -qx cloudflared; then
	docker ps -a --filter 'name=cloudflared' \
		--format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
	echo
	docker inspect cloudflared \
		--format 'State: {{.State.Status}} | Exit: {{.State.ExitCode}} | Restarts: {{.RestartCount}} | StartedAt: {{.State.StartedAt}}'
else
	echo "(no cloudflared container found)"
fi

section IMAGE_PULLABILITY
image=$(grep -E '^IMG_CLOUDFLARED=' "${HOMELAB_DIR:-$HOME/homelab}/.env" 2>/dev/null | cut -d= -f2-)
echo "IMG_CLOUDFLARED=${image:-<unset>}"
case "${image:-}" in
	*'<digest>'*|*'sha256:<'*)
		echo '!! PLACEHOLDER DIGEST — this is the probable root cause of 1033.'
		echo '   Replace with a real pinned digest, e.g.'
		echo '   docker pull cloudflare/cloudflared:latest && docker inspect --format "{{index .RepoDigests 0}}" cloudflare/cloudflared:latest'
		;;
	'')
		echo '!! IMG_CLOUDFLARED is unset — docker compose will fall back to the default in core.yml.'
		;;
	*)
		echo 'Image string looks concrete; try a pull:'
		docker pull "$image" 2>&1 | tail -3
		;;
esac

section TOKEN
token=$(grep -E '^CF_TUNNEL_TOKEN=' "${HOMELAB_DIR:-$HOME/homelab}/.env" 2>/dev/null | cut -d= -f2-)
if [ -z "$token" ]; then
	echo '!! CF_TUNNEL_TOKEN is empty — cloudflared cannot authenticate.'
else
	printf 'CF_TUNNEL_TOKEN=<%d chars>\n' "${#token}"
fi

section CONFIG
cat "${HOMELAB_DIR:-$HOME/homelab}/config/cloudflared/config.yml" 2>/dev/null | head -40 || echo '(config.yml not found)'

section LOGS_LAST_50
docker logs --tail 50 cloudflared 2>&1 || echo '(no logs)'

section CONNECTIVITY
echo '# Host → Cloudflare edge'
curl -sS -o /dev/null -w 'dns=%{remote_ip} http=%{http_code} connect=%{time_connect}\n' \
	https://api.cloudflare.com/ 2>&1 | head -3

echo '# Host → tunnel origin (from inside container if up)'
docker exec cloudflared wget -q -O - http://homepage:3000 2>&1 | head -3 || echo '(exec failed)'

section SYSTEMD_OR_DOCKERD
systemctl is-active docker 2>/dev/null || echo '(docker unit unknown)'

section CF_DASHBOARD_HINT
cat <<'HINT'

Next-step triage:
  1. If IMG_CLOUDFLARED has <digest> placeholder → fix .env and `docker compose up -d cloudflared`.
  2. If CF_TUNNEL_TOKEN empty → regenerate in Cloudflare Zero Trust → Networks → Tunnels → <tunnel> → Install connector.
  3. If container is "Exited (0)" right away → token mismatch (tunnel deleted in dash).
  4. If container is "Restarting" with "ERR connection refused" → origin service down, not cloudflared.
  5. If host cannot reach api.cloudflare.com → upstream network issue, not cloudflared.
HINT
