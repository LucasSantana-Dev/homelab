#!/bin/bash
# Runtime status for SSO edge rollout components.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
ENV_FILE="${PROJECT_ROOT}/.env"
CF_CONFIG_FILE="${PROJECT_ROOT}/config/cloudflared/config.yml"

status_ok=0
status_warn=0
status_fail=0

log() {
    printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

ok() {
    status_ok=$((status_ok + 1))
    log "OK: $*"
}

warn() {
    status_warn=$((status_warn + 1))
    log "WARN: $*"
}

fail() {
    status_fail=$((status_fail + 1))
    log "FAIL: $*"
}

env_value() {
    local key="$1"
    if [ ! -f "${ENV_FILE}" ]; then
        return
    fi
    awk -F= -v k="${key}" '
        $0 ~ /^[[:space:]]*#/ { next }
        $1 == k { value = substr($0, index($0, "=") + 1) }
        END { if (value != "") print value }
    ' "${ENV_FILE}" | tr -d '\r' | sed -E 's/^[[:space:]]+|[[:space:]]+$//g; s/^"(.*)"$/\1/; s/^'\''(.*)'\''$/\1/'
}

check_non_empty_env() {
    local key="$1"
    local value
    value="$(env_value "${key}")"
    if [ -n "${value}" ]; then
        ok "${key} is configured"
    else
        fail "${key} is empty in .env"
    fi
}

container_running() {
    local name="$1"
    local state
    state="$(docker inspect -f '{{.State.Status}}' "${name}" 2>/dev/null || true)"
    if [ "${state}" = "running" ]; then
        ok "Container ${name} is running"
    else
        fail "Container ${name} is not running (state=${state:-missing})"
    fi
}

is_container_running() {
    local name="$1"
    [ "$(docker inspect -f '{{.State.Status}}' "${name}" 2>/dev/null || true)" = "running" ]
}

log "SSO edge status"
log "==============="

if ! command -v docker >/dev/null 2>&1; then
    fail "docker is not available"
    exit 1
fi

check_non_empty_env "CF_TUNNEL_TOKEN"
check_non_empty_env "AUTHENTIK_ALLOWED_EMAIL"
check_non_empty_env "AUTHENTIK_ALLOWED_GITHUB_USERNAME"
check_non_empty_env "AUTHENTIK_SESSION_DAYS"
check_non_empty_env "AUTHENTIK_REQUIRE_MFA"
check_non_empty_env "AUTHENTIK_GRAFANA_CLIENT_ID"
check_non_empty_env "AUTHENTIK_GRAFANA_CLIENT_SECRET"
check_non_empty_env "AUTHENTIK_PORTAINER_CLIENT_ID"
check_non_empty_env "AUTHENTIK_PORTAINER_CLIENT_SECRET"

domain="$(env_value DOMAIN)"
if [ -z "${domain}" ]; then
    domain="luk-homeserver.com.br"
fi
outpost_probe_host="grafana.${domain}"

container_running "nginx-proxy"
container_running "authentik-server"
container_running "cloudflared"

if [ -f "${CF_CONFIG_FILE}" ]; then
    host_count="$(grep -c '^[[:space:]]*- hostname:' "${CF_CONFIG_FILE}" || true)"
    if [ "${host_count}" -eq 10 ]; then
        ok "Cloudflared ingress has expected 10 published hostnames"
    else
        fail "Cloudflared ingress host count is ${host_count} (expected 10)"
    fi
else
    fail "Missing ${CF_CONFIG_FILE}"
fi

outpost_status=""
if is_container_running "nginx-proxy"; then
    outpost_status="$(curl -k -sS -o /dev/null -w "%{http_code}" "https://127.0.0.1:8443/outpost.goauthentik.io/auth/nginx" -H "Host: ${outpost_probe_host}" || true)"
elif is_container_running "authentik-server"; then
    outpost_status="$(docker exec -i -e AK_OUTPOST_HOST="${outpost_probe_host}" authentik-server python3 - <<'PY' 2>/dev/null || true
import urllib.request, urllib.error
import os
url = "http://localhost:9000/outpost.goauthentik.io/auth/nginx"
host = os.getenv("AK_OUTPOST_HOST", "")
req = urllib.request.Request(url, headers={"Host": host} if host else {})
try:
    with urllib.request.urlopen(req, timeout=5) as response:
        print(response.getcode())
except urllib.error.HTTPError as error:
    print(error.code)
except Exception:
    print("ERR")
PY
)"
fi

case "${outpost_status}" in
    200|204|302|401|403)
        ok "Authentik outpost endpoint is active (status=${outpost_status})"
        ;;
    404)
        fail "Authentik outpost endpoint is still 404 (proxy provider/outpost missing)"
        ;;
    "")
        warn "Authentik outpost endpoint could not be checked (authentik-server unavailable)"
        ;;
    *)
        warn "Authentik outpost endpoint returned ${outpost_status}"
        ;;
esac

log ""
log "Summary: ok=${status_ok} warn=${status_warn} fail=${status_fail}"

if [ "${status_fail}" -gt 0 ]; then
    exit 1
fi
