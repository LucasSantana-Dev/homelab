#!/bin/bash
# Issue/renew a wildcard Let's Encrypt certificate via Cloudflare DNS-01.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
ENV_FILE="${PROJECT_ROOT}/.env"
SSL_DIR="${PROJECT_ROOT}/config/nginx/ssl"

log() {
    printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
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

if [ ! -f "${ENV_FILE}" ]; then
    echo "ERROR: ${ENV_FILE} not found"
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker command is required"
    exit 1
fi

domain="$(env_value DOMAIN)"
cf_token="$(env_value CLOUDFLARE_API_TOKEN)"
certbot_email="$(env_value CERTBOT_EMAIL)"
if [ -z "${certbot_email}" ]; then
    certbot_email="$(env_value AUTHENTIK_ALLOWED_EMAIL)"
fi

if [ -z "${domain}" ]; then
    echo "ERROR: DOMAIN is empty in .env"
    exit 1
fi

if [ -z "${cf_token}" ]; then
    echo "ERROR: CLOUDFLARE_API_TOKEN is empty in .env"
    exit 1
fi

if [ -f "${SSL_DIR}/renewal/${domain}-0001.conf" ]; then
    cert_name="${domain}-0001"
elif [ -s "${SSL_DIR}/renewal/${domain}.conf" ]; then
    cert_name="${domain}"
elif [ -d "${SSL_DIR}/live/${domain}" ]; then
    cert_name="${domain}-0001"
else
    cert_name="${domain}"
fi

propagation_seconds="${CERTBOT_DNS_PROPAGATION_SECONDS:-30}"

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT
printf 'dns_cloudflare_api_token = %s\n' "${cf_token}" > "${tmpdir}/cloudflare.ini"
chmod 600 "${tmpdir}/cloudflare.ini"

log "Issuing/renewing wildcard cert for ${domain} (cert-name=${cert_name})"
certbot_args=(
    certonly
    --non-interactive
    --agree-tos
    --dns-cloudflare
    --dns-cloudflare-credentials /tmp/cf/cloudflare.ini
    --dns-cloudflare-propagation-seconds "${propagation_seconds}"
    --cert-name "${cert_name}"
    --keep-until-expiring
    -d "${domain}"
    -d "*.${domain}"
)
if [ -n "${certbot_email}" ]; then
    certbot_args+=(--email "${certbot_email}")
else
    certbot_args+=(--register-unsafely-without-email)
fi

docker run --rm \
    -v "${SSL_DIR}:/etc/letsencrypt" \
    -v "${tmpdir}:/tmp/cf:ro" \
    certbot/dns-cloudflare "${certbot_args[@]}"

log "Syncing nginx certificate paths"
docker run --rm \
    -v "${SSL_DIR}:/etc/letsencrypt" \
    alpine:3.20 sh -eu -c '
        cert_name="$1"
        domain="$2"
        mkdir -p "/etc/letsencrypt/live/${domain}"
        ln -sfn "../${cert_name}/fullchain.pem" "/etc/letsencrypt/live/${domain}/fullchain.pem"
        ln -sfn "../${cert_name}/privkey.pem" "/etc/letsencrypt/live/${domain}/privkey.pem"
        cp -f "/etc/letsencrypt/live/${cert_name}/fullchain.pem" "/etc/letsencrypt/fullchain.pem"
        cp -f "/etc/letsencrypt/live/${cert_name}/privkey.pem" "/etc/letsencrypt/privkey.pem"
        chmod 600 /etc/letsencrypt/privkey.pem
    ' _ "${cert_name}" "${domain}"

if docker inspect -f '{{.State.Status}}' nginx-proxy 2>/dev/null | grep -q '^running$'; then
    log "Restarting nginx-proxy to apply the renewed certificate"
    (
        cd "${PROJECT_ROOT}"
        docker compose restart nginx >/dev/null
    )
else
    log "nginx-proxy is not running; skip restart"
fi

cert_file="${SSL_DIR}/live/${cert_name}/fullchain.pem"
if [ -f "${cert_file}" ]; then
    log "Active certificate details"
    openssl x509 -in "${cert_file}" -noout -subject -issuer -dates -ext subjectAltName
fi

log "Certificate renewal flow completed"
