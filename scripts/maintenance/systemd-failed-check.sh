#!/usr/bin/env bash
# systemd-failed-check.sh — one dead-man that watches EVERY systemd unit.
# Pings a single Healthchecks check: success when nothing is failed, /fail
# (with the failed-unit list as the body) when any unit is in failed state.
# Run it from cron every ~15min; if it stops pinging OR reports failures, the
# self-hosted Healthchecks instance emails. Catches the whole class that bit us
# 2026-07-09 (watchdog, kopia-offsite, homelab-docker, k3s-health all failed
# silently because nobody watched `systemctl --failed`).
#
#   systemd-failed-check.sh            # system units
#   SYSTEMD_SCOPE=user  ...            # user units instead
#
# Env (from ~/homelab/.env — ping key is a project secret):
#   HEALTHCHECKS_PING_KEY   project Ping Key
#   HEALTHCHECKS_URL        base URL (default http://localhost:${HEALTHCHECKS_PORT:-8092})
#   HC_SLUG                 check slug (default systemd-failed-units)
# Fail-open: no key -> just prints status, exits by failure count.
set -euo pipefail

: "${HEALTHCHECKS_URL:=http://localhost:${HEALTHCHECKS_PORT:-8092}}"
: "${HC_SLUG:=systemd-failed-units}"
key="${HEALTHCHECKS_PING_KEY:-}"
base="${HEALTHCHECKS_URL%/}"
scope_flag=""; [[ "${SYSTEMD_SCOPE:-system}" == "user" ]] && scope_flag="--user"

# shellcheck disable=SC2086
failed="$(systemctl $scope_flag list-units --state=failed --no-legend --plain 2>/dev/null | awk '{print $1}' | grep -v '^$' || true)"
count="$(printf '%s' "$failed" | grep -c . || true)"

if [[ "$count" -eq 0 ]]; then
  body="OK: no failed units"
  suffix=""
else
  body="FAILED units ($count):"$'\n'"$failed"
  suffix="/fail"
fi
echo "$body"

if [[ -n "$key" ]]; then
  printf '%s' "$body" | curl -fsS -m 10 --retry 3 -o /dev/null \
    --data-binary @- "${base}/ping/${key}/${HC_SLUG}${suffix}?create=1" 2>/dev/null || true
fi
exit "$count"
