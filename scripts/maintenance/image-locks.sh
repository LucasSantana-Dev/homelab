#!/bin/bash
# Image lock maintenance helpers for critical homelab services.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOMELAB_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
ENV_FILE="${HOMELAB_DIR}/.env"

LOCK_KEYS=(
    "IMG_CLOUDFLARED"
    "IMG_HOMEASSISTANT"
    "IMG_PIHOLE"
    "IMG_POSTGRES_15_ALPINE"
    "IMG_REDIS_ALPINE"
    "IMG_NEXTCLOUD"
    "IMG_MARIADB"
    "IMG_N8N"
    "IMG_GRAFANA"
    "IMG_PORTAINER"
    "IMG_PROMETHEUS"
    "IMG_ALERTMANAGER"
    "IMG_CADVISOR"
    "IMG_PAPERLESS_BASE"
    "IMG_BLACKBOX"
    "IMG_CADDY"
    "IMG_CROWDSEC"
    "IMG_GATUS"
    "IMG_HEALTHCHECKS"
    "IMG_HOMEPAGE"
    "IMG_KOPIA"
    "IMG_LOKI"
    "IMG_NODE_EXPORTER"
    "IMG_PROMTAIL"
    "IMG_STREMIO"
    "IMG_TINYAUTH"
    "IMG_WUD"
)

declare -A KEY_DEFAULTS=(
    [IMG_CLOUDFLARED]="cloudflare/cloudflared:latest"
    [IMG_HOMEASSISTANT]="ghcr.io/home-assistant/home-assistant:stable"
    [IMG_PIHOLE]="pihole/pihole:latest"
    [IMG_POSTGRES_15_ALPINE]="postgres:15-alpine"
    [IMG_REDIS_ALPINE]="redis:alpine"
    [IMG_NEXTCLOUD]="nextcloud:latest"
    [IMG_MARIADB]="mariadb:latest"
    [IMG_N8N]="n8nio/n8n:latest"
    [IMG_GRAFANA]="grafana/grafana-oss:latest"
    [IMG_PORTAINER]="portainer/portainer-ce:latest"
    [IMG_PROMETHEUS]="prom/prometheus:latest"
    [IMG_ALERTMANAGER]="prom/alertmanager:latest"
    [IMG_CADVISOR]="gcr.io/cadvisor/cadvisor:latest"
    [IMG_PAPERLESS_BASE]="ghcr.io/paperless-ngx/paperless-ngx:latest"
    [IMG_BLACKBOX]="prom/blackbox-exporter:v0.28.0"
    [IMG_CADDY]="caddy:2.10.2-alpine"
    [IMG_CROWDSEC]="crowdsecurity/crowdsec:v1.7.8"
    [IMG_GATUS]="twinproduction/gatus:v5.36.0"
    [IMG_HEALTHCHECKS]="healthchecks/healthchecks:v4.2"
    [IMG_HOMEPAGE]="ghcr.io/gethomepage/homepage:v1.13.2"
    [IMG_KOPIA]="kopia/kopia:0.21.1"
    [IMG_LOKI]="grafana/loki:3.7.2"
    [IMG_NODE_EXPORTER]="prom/node-exporter:v1.9.1"
    [IMG_PROMTAIL]="grafana/promtail:3.6.11"
    [IMG_STREMIO]="stremio/server:v4.21.0"
    [IMG_TINYAUTH]="ghcr.io/steveiliop56/tinyauth:v5.0.7"
    [IMG_WUD]="fmartinou/whats-up-docker:6.6.1"
)

declare -A KEY_CONTAINERS=(
    [IMG_CLOUDFLARED]="cloudflared"
    [IMG_HOMEASSISTANT]="homeassistant"
    [IMG_PIHOLE]="pihole"
    [IMG_POSTGRES_15_ALPINE]="paperless-db healthchecks-db"
    [IMG_REDIS_ALPINE]="nextcloud-redis paperless-redis"
    [IMG_NEXTCLOUD]="nextcloud"
    [IMG_MARIADB]="nextcloud-db"
    [IMG_N8N]="n8n"
    [IMG_GRAFANA]="grafana"
    [IMG_PORTAINER]="portainer"
    [IMG_PROMETHEUS]="prometheus"
    [IMG_ALERTMANAGER]="alertmanager"
    [IMG_CADVISOR]="cadvisor"
    [IMG_PAPERLESS_BASE]="paperless-ngx"
    [IMG_BLACKBOX]="blackbox-exporter"
    [IMG_CADDY]="caddy-lan"
    [IMG_CROWDSEC]="crowdsec"
    [IMG_GATUS]="gatus"
    [IMG_HEALTHCHECKS]="healthchecks"
    [IMG_HOMEPAGE]="homepage"
    [IMG_KOPIA]="kopia"
    [IMG_LOKI]="loki"
    [IMG_NODE_EXPORTER]="node-exporter"
    [IMG_PROMTAIL]="promtail"
    [IMG_STREMIO]="stremio-server"
    [IMG_TINYAUTH]="tinyauth"
    [IMG_WUD]="whats-up-docker"
)

usage() {
    cat <<'USAGE'
Usage:
  image-locks.sh status
  image-locks.sh refresh --dry-run
  image-locks.sh refresh --apply
USAGE
}

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

upsert_env_key() {
    local key="$1"
    local value="$2"
    local file="$3"
    local tmp_file
    local file_mode

    tmp_file="$(mktemp)"
    file_mode="$(stat -c '%a' "$file" 2>/dev/null || echo '600')"

    awk -F= -v k="${key}" -v v="${value}" '
        BEGIN { done = 0 }
        {
            if ($0 ~ /^[[:space:]]*#/) {
                print $0
                next
            }
            if ($1 == k) {
                if (done == 0) {
                    print k "=" v
                    done = 1
                }
                next
            }
            print $0
        }
        END {
            if (done == 0) {
                print k "=" v
            }
        }
    ' "$file" > "$tmp_file"

    mv "$tmp_file" "$file"
    chmod "$file_mode" "$file" 2>/dev/null || true
}

has_digest_lock() {
    local ref="$1"
    [[ "$ref" =~ @sha256:[a-f0-9]{64}$ ]]
}

strip_digest() {
    local ref="$1"
    echo "${ref%%@sha256:*}"
}

resolve_locked_ref() {
    local repo_tag="$1"
    local repo_digest digest

    docker pull "$repo_tag" >/dev/null
    repo_digest="$(docker image inspect -f '{{index .RepoDigests 0}}' "$repo_tag" 2>/dev/null || true)"

    if [ -z "$repo_digest" ] || [[ "$repo_digest" != *@sha256:* ]]; then
        return 1
    fi

    digest="${repo_digest##*@}"
    printf "%s@%s" "$repo_tag" "$digest"
}

status_for_key() {
    local key="$1"
    local configured ref lock_state containers aligned_count total_count align_state
    local target_image_id running_image_id container

    configured="$(env_value "$key")"
    if [ -z "$configured" ]; then
        ref="${KEY_DEFAULTS[$key]}"
    else
        ref="$configured"
    fi

    if has_digest_lock "$ref"; then
        lock_state="locked"
    else
        lock_state="unlocked"
    fi

    containers="${KEY_CONTAINERS[$key]:-}"
    if [ -z "$containers" ]; then
        align_state="n/a"
    else
        target_image_id="$(docker image inspect -f '{{.Id}}' "$ref" 2>/dev/null || true)"
        aligned_count=0
        total_count=0

        for container in $containers; do
            total_count=$((total_count + 1))
            running_image_id="$(docker inspect -f '{{.Image}}' "$container" 2>/dev/null || true)"
            if [ -n "$target_image_id" ] && [ -n "$running_image_id" ] && [ "$target_image_id" = "$running_image_id" ]; then
                aligned_count=$((aligned_count + 1))
            fi
        done

        if [ "$total_count" -eq 0 ]; then
            align_state="n/a"
        elif [ "$aligned_count" -eq "$total_count" ]; then
            align_state="aligned(${aligned_count}/${total_count})"
        else
            align_state="drift(${aligned_count}/${total_count})"
        fi
    fi

    printf "%-26s %-10s %-16s %s\n" "$key" "$lock_state" "$align_state" "$ref"
}

run_status() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "docker is required" >&2
        exit 1
    fi

    if [ ! -f "$ENV_FILE" ]; then
        echo "Missing ${ENV_FILE}" >&2
        exit 1
    fi

    log "Image lock status"
    printf "%-26s %-10s %-16s %s\n" "KEY" "LOCK" "RUNTIME" "REFERENCE"
    printf "%-26s %-10s %-16s %s\n" "--------------------------" "----------" "----------------" "---------"

    local key
    for key in "${LOCK_KEYS[@]}"; do
        status_for_key "$key"
    done
}

run_refresh() {
    local mode="$1"
    local key current_ref repo_tag new_ref changed_count

    changed_count=0
    for key in "${LOCK_KEYS[@]}"; do
        current_ref="$(env_value "$key")"
        if [ -z "$current_ref" ]; then
            current_ref="${KEY_DEFAULTS[$key]}"
        fi

        repo_tag="$(strip_digest "$current_ref")"
        # Fail closed on :latest (#213). Pinning the digest of a moving `:latest`
        # tag gives no version traceability and silently undermines reproducible
        # pinning. Require a concrete tag in .env instead.
        case "$repo_tag" in
            *:latest)
                echo "Refusing to pin ${key} at ':latest' (${repo_tag}) — set a concrete version tag in .env (':latest' is a moving target; pinning its digest defeats reproducibility)." >&2
                exit 1
                ;;
        esac
        if ! new_ref="$(resolve_locked_ref "$repo_tag")"; then
            echo "Failed to resolve digest for ${key} (${repo_tag})" >&2
            exit 1
        fi

        if [ "$current_ref" != "$new_ref" ]; then
            changed_count=$((changed_count + 1))
            if [ "$mode" = "apply" ]; then
                upsert_env_key "$key" "$new_ref" "$ENV_FILE"
            fi
            printf "%s\n  old: %s\n  new: %s\n" "$key" "$current_ref" "$new_ref"
        else
            printf "%s\n  unchanged: %s\n" "$key" "$current_ref"
        fi
    done

    if [ "$mode" = "apply" ]; then
        log "Refresh complete: ${changed_count} key(s) updated in ${ENV_FILE}"
    else
        log "Dry-run complete: ${changed_count} key(s) would change"
    fi
}

case "${1:-}" in
    status)
        run_status
        ;;
    refresh)
        case "${2:-}" in
            --dry-run)
                run_refresh dry-run
                ;;
            --apply)
                run_refresh apply
                ;;
            *)
                usage
                exit 1
                ;;
        esac
        ;;
    *)
        usage
        exit 1
        ;;
esac
