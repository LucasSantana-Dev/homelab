#!/bin/bash
# Smoke tests for proxy SSO protections and Authentik edge routing.

set -euo pipefail

status_ok=0
status_fail=0

log() {
    printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

ok() {
    status_ok=$((status_ok + 1))
    log "OK: $*"
}

fail() {
    status_fail=$((status_fail + 1))
    log "FAIL: $*"
}

protected_hosts=(
    "luk-homeserver.com.br"
    "www.luk-homeserver.com.br"
    "homeassistant.luk-homeserver.com.br"
    "grafana.luk-homeserver.com.br"
    "portainer.luk-homeserver.com.br"
    "n8n.luk-homeserver.com.br"
    "cloud.luk-homeserver.com.br"
    "docs.luk-homeserver.com.br"
    "vault.luk-homeserver.com.br"
)

log "SSO smoke test"
log "=============="

if ! docker exec nginx-proxy nginx -t >/tmp/nginx_sso_test.log 2>&1; then
    fail "nginx -t failed inside nginx-proxy (see /tmp/nginx_sso_test.log)"
else
    ok "nginx -t passed"
fi

for host in "${protected_hosts[@]}"; do
    response_headers="$(curl -k -sS -o /dev/null -D - "https://127.0.0.1:8443/" -H "Host: ${host}" || true)"
    status_code="$(printf "%s\n" "${response_headers}" | awk 'toupper($1) ~ /^HTTP/ {print $2; exit}')"
    location_header="$(printf "%s\n" "${response_headers}" | awk 'tolower($1)=="location:" {print $2; exit}' | tr -d '\r')"

    if [[ "${status_code}" =~ ^30[1278]$ ]] && [[ "${location_header}" == https://auth.luk-homeserver.com.br/outpost.goauthentik.io/start* || "${location_header}" == */outpost.goauthentik.io/start* ]]; then
        ok "${host} redirects unauthenticated requests to Authentik"
    else
        fail "${host} did not return expected Authentik redirect (status=${status_code:-none}, location=${location_header:-none})"
    fi
done

outpost_code="$(curl -k -sS -o /dev/null -w "%{http_code}" "https://127.0.0.1:8443/outpost.goauthentik.io/auth/nginx" -H "Host: grafana.luk-homeserver.com.br" || true)"
if [ "${outpost_code}" != "404" ] && [ -n "${outpost_code}" ]; then
    ok "Outpost endpoint is reachable via nginx (status=${outpost_code})"
else
    fail "Outpost endpoint is not active via nginx (status=${outpost_code:-none})"
fi

if docker inspect -f '{{.State.Status}}' cloudflared 2>/dev/null | grep -q '^running$'; then
    ok "cloudflared container is running"
else
    fail "cloudflared container is not running"
fi

log ""
log "Summary: ok=${status_ok} fail=${status_fail}"
if [ "${status_fail}" -gt 0 ]; then
    exit 1
fi
