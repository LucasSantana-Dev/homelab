#!/bin/bash
# wait-for-bind-ip.sh
# Block (up to WAIT_BIND_IP_TIMEOUT seconds) until BIND_IP from .env is
# assigned to an interface, so `docker compose up` can publish ports on it.
#
# Why: several services publish on ${BIND_IP} (the Tailscale address on this
# host). homelab-docker.service ran After=tailscaled.service plus a fixed
# `sleep 10`, but tailscaled being started does not mean tailscale0 has its
# address; publishing then fails with "cannot assign requested address"
# (the 2026-09-20 outage started this way). Loopback and wildcard values need
# no wait. Never fails the unit: on timeout it warns and lets compose try.

set -uo pipefail

ENV_FILE="${ENV_FILE:-/home/luk-server/homelab/.env}"
TIMEOUT="${WAIT_BIND_IP_TIMEOUT:-120}"
[[ "$TIMEOUT" =~ ^[0-9]+$ ]] || TIMEOUT=120 # a typo must not fail the unit

bind_ip="$(grep -E '^BIND_IP=' "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d "\"' ")"
case "$bind_ip" in
  "" | 127.* | 0.0.0.0)
    echo "wait-for-bind-ip: BIND_IP=${bind_ip:-unset}, nothing to wait for"
    exit 0
    ;;
esac

for ((i = 0; i < TIMEOUT; i++)); do
  if ip -4 -o addr show 2>/dev/null | grep -qwF -- "$bind_ip"; then
    echo "wait-for-bind-ip: $bind_ip is up after ${i}s"
    exit 0
  fi
  sleep 1
done
echo "wait-for-bind-ip: $bind_ip not assigned after ${TIMEOUT}s, continuing anyway" >&2
exit 0
