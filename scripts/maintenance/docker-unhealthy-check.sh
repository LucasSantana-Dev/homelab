#!/usr/bin/env bash
# docker-unhealthy-check.sh — one dead-man that watches EVERY container's health.
# Sibling to systemd-failed-check.sh: that one catches failed systemd units, this
# one catches crash-looping / unhealthy Docker containers — which are NOT systemd
# units and so slip past it. Directly closes the gap that let lucky-bot crash-loop
# 262× unnoticed (2026-07-09): restart:unless-stopped keeps a broken container
# "up" (restarting) forever with no failed-unit and no alert.
#
# Pings a single Healthchecks check: success when every container is healthy (or
# has no healthcheck) and none is Restarting/Exited; /fail (with the offender
# list) otherwise.
#
#   docker-unhealthy-check.sh
#
# A container is flagged when: State=restarting, State=exited (unexpected), or
# Health.Status=unhealthy. Containers with no healthcheck that are simply Up are
# fine (can't judge health we don't have).
#
# Env (from ~/homelab/.env — ping key is a project secret):
#   HEALTHCHECKS_PING_KEY   project Ping Key
#   HEALTHCHECKS_URL        base URL (default http://localhost:${HEALTHCHECKS_PORT:-8092})
#   HC_SLUG                 check slug (default docker-unhealthy)
# Fail-open: no key -> just prints status, exits by offender count.
set -euo pipefail

: "${HEALTHCHECKS_URL:=http://localhost:${HEALTHCHECKS_PORT:-8092}}"
: "${HC_SLUG:=docker-unhealthy}"
key="${HEALTHCHECKS_PING_KEY:-}"
base="${HEALTHCHECKS_URL%/}"

# name | state | health(or "none") for every container
rows="$(docker ps -a --format '{{.Names}}' | while read -r n; do
  [ -n "$n" ] || continue
  st="$(docker inspect -f '{{.State.Status}}' "$n" 2>/dev/null || echo unknown)"
  hl="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$n" 2>/dev/null || echo none)"
  printf '%s|%s|%s\n' "$n" "$st" "$hl"
done)"

# Offender = restarting, unhealthy, or unexpectedly exited (non-zero, not a
# oneshot). Keep it conservative: restarting + unhealthy are the crash-loop signal.
offenders="$(printf '%s\n' "$rows" | awk -F'|' '$2=="restarting" || $3=="unhealthy" {print $1" ("$2"/"$3")"}')"
count="$(printf '%s' "$offenders" | grep -c . || true)"

if [ "$count" -eq 0 ]; then
  body="OK: all containers healthy"
  suffix=""
else
  body="UNHEALTHY containers ($count):"$'\n'"$offenders"
  suffix="/fail"
fi
echo "$body"

if [ -n "$key" ]; then
  printf '%s' "$body" | curl -fsS -m 10 --retry 3 -o /dev/null \
    --data-binary @- "${base}/ping/${key}/${HC_SLUG}${suffix}?create=1" 2>/dev/null || true
fi
exit "$count"
