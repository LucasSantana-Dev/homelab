#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/disk-trend-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting disk trend check..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

TREND_CSV="/home/luk-server/agent-logs/disk-trend.csv"
[[ -f "$TREND_CSV" ]] || echo "date,pct_used,used_gb,total_gb" > "$TREND_CSV"

PCT=$(df / --output=pcent | tail -1 | tr -d ' %')
USED=$(df / --output=used  | tail -1 | tr -d ' ')
TOTAL=$(df / --output=size  | tail -1 | tr -d ' ')
USED_GB=$(( USED  / 1024 / 1024 ))
TOTAL_GB=$(( TOTAL / 1024 / 1024 ))

echo "$(date +%Y-%m-%d),$PCT,$USED_GB,$TOTAL_GB" >> "$TREND_CSV"
echo "Disk: ${PCT}% (${USED_GB}GB / ${TOTAL_GB}GB)"

if [[ "$PCT" -ge 85 ]]; then
    $NOTIFY --title "🔴 Disk Critical" \
        --body "/ is at ${PCT}% (${USED_GB}GB / ${TOTAL_GB}GB)" \
        --urgency alert || true
    echo "[$(date)] Discord alerted — disk at ${PCT}%."
elif [[ "$PCT" -ge 80 ]]; then
    $NOTIFY --title "⚠️ Disk Warning" \
        --body "/ is at ${PCT}% (${USED_GB}GB / ${TOTAL_GB}GB)" \
        --urgency warn || true
    echo "[$(date)] Discord warned — disk at ${PCT}%."
else
    echo "[$(date)] Disk healthy — no alert."
fi

# Weekly trend summary (Fridays)
if [[ "$(date +%u)" == "5" ]] && [[ -f "$TREND_CSV" ]]; then
    SUMMARY=$(tail -7 "$TREND_CSV" | awk -F, 'NR>0{print $1": "$2"%"}' | tr '\n' ' ')
    $NOTIFY --title "📈 Disk Trend (7d)" --body "$SUMMARY" --urgency info || true
fi

echo "[$(date)] Disk trend check complete."
