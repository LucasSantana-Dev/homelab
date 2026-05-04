#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/cert-expiry-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Checking TLS certificate expiry..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

DOMAINS="lucky-api.lucassantana.tech"
WARN_DAYS=30
ISSUES=""

for domain in $DOMAINS; do
    expiry=$(echo | openssl s_client -connect "${domain}:443" -servername "$domain" 2>/dev/null \
        | openssl x509 -noout -enddate 2>/dev/null \
        | cut -d= -f2) || expiry=""

    if [[ -z "$expiry" ]]; then
        echo "[$domain] ERROR: could not fetch cert"
        ISSUES="${ISSUES}• ${domain}: cert unreachable\n"
        continue
    fi

    expiry_epoch=$(date -d "$expiry" +%s 2>/dev/null) || expiry_epoch=0
    now_epoch=$(date +%s)
    days_left=$(( (expiry_epoch - now_epoch) / 86400 ))

    echo "[$domain] expires in ${days_left} days ($expiry)"

    if [[ "$days_left" -le "$WARN_DAYS" ]]; then
        ISSUES="${ISSUES}• ${domain}: ${days_left} days left\n"
    fi
done

if [[ -n "$ISSUES" ]]; then
    BODY=$(printf '%b' "$ISSUES")
    URGENCY="warn"
    [[ "$BODY" =~ "unreachable" ]] && URGENCY="alert"
    $NOTIFY --title "🔐 TLS Cert Expiry Warning" --body "$BODY" --urgency "$URGENCY" || true
    echo "[$(date)] Discord alerted on cert expiry."
else
    echo "[$(date)] All certs healthy."
fi
echo "[$(date)] Cert expiry check complete."
