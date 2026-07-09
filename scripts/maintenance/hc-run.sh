#!/usr/bin/env bash
# hc-run.sh — wrap a scheduled job with Healthchecks liveness pings so silent
# job death self-reports (generalizes the ADR-0026 dead-man pattern to every
# cron/timer). If the job stops running or starts failing, the self-hosted
# Healthchecks instance alarms via email — independent of Discord.
#
#   hc-run.sh <slug> -- <command> [args...]
#
# Pings, using slug-based auto-provisioning (ONE project ping key, checks
# auto-create on first ping):
#   <base>/ping/<key>/<slug>/start   before the command
#   <base>/ping/<key>/<slug>         on success (exit 0), last output as body
#   <base>/ping/<key>/<slug>/fail    on failure, exit code + output as body
#
# Env (from ~/homelab/.env — never committed; ping key is a project secret):
#   HEALTHCHECKS_PING_KEY   project Ping Key (Healthchecks → project → Ping key)
#   HEALTHCHECKS_URL        base URL (default http://localhost:${HEALTHCHECKS_PORT:-8092})
#
# Fail-open by design: if HEALTHCHECKS_PING_KEY is unset, the job STILL runs
# (unwrapped) — liveness reporting must never block the actual work.
set -euo pipefail

if [[ $# -lt 3 || "${2}" != "--" ]]; then
  echo "usage: hc-run.sh <slug> -- <command> [args...]" >&2
  exit 2
fi
slug="$1"; shift 2

# Cron runs with a minimal environment, so HEALTHCHECKS_PING_KEY (a ~/homelab/.env
# secret) is unset there and every wrapped job would run but silently never ping.
# Source .env here — the single choke point all wrapped jobs pass through — so the
# ping key is available regardless of the caller's environment.
env_file="${HOMELAB_DIR:-$HOME/homelab}/.env"
if [[ -z "${HEALTHCHECKS_PING_KEY:-}" && -r "$env_file" ]]; then
  set -a; # shellcheck disable=SC1090
  source "$env_file"; set +a
fi

: "${HEALTHCHECKS_URL:=http://localhost:${HEALTHCHECKS_PORT:-8092}}"
key="${HEALTHCHECKS_PING_KEY:-}"
base="${HEALTHCHECKS_URL%/}"

# $1 = path suffix ("/start" | "" | "/fail"); reads body on stdin when piped.
# Always drains stdin (even with no key) so a piping producer never hits SIGPIPE.
hc_ping() {
  if [[ -z "$key" ]]; then
    cat >/dev/null 2>&1 || true
    return 0
  fi
  curl -fsS -m 10 --retry 3 --retry-delay 2 -o /dev/null \
    --data-binary @- "${base}/ping/${key}/${slug}${1}?create=1" 2>/dev/null || true
}

hc_ping "/start" </dev/null

log="$(mktemp)"
trap 'rm -f "$log"' EXIT

set +e
"$@" >"$log" 2>&1
rc=$?
set -e

# Body capped so a chatty job can't POST megabytes.
{ tail -c 10000 "$log" | hc_ping "$( [[ $rc -eq 0 ]] && echo "" || echo "/fail" )"; } || true

cat "$log"
exit "$rc"
