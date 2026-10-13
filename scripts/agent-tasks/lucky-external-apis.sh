#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/lucky-external-apis-$(date +%Y%m%d-%H%M%S).log"

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

log_info "Checking Lucky external API dependencies..."

ISSUES=""

check_api() {
	local name="$1" url="$2" ok_codes="$3"
	local code
	code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null) || code="000"
	log_info "[$name] HTTP $code"
	# Plain string match, no pipe: under `set -o pipefail`, `echo | grep -q`
	# can fail when grep exits early and echo gets SIGPIPE (false alarms).
	if [[ " $ok_codes " != *" $code "* ]]; then
		ISSUES="${ISSUES}• ${name}: HTTP ${code}\n"
	fi
}

# Spotify API — 401 = up (auth required), anything else = problem.
# The bare /v1/ root answers 410 Gone since 2026-10, so probe a real endpoint.
check_api "Spotify" "https://api.spotify.com/v1/search?q=a&type=track" "401"

# Last.fm API — 400 = up (parameterless requests return 400, not 200)
check_api "Last.fm" "https://ws.audioscrobbler.com/2.0/" "400"

# Discord API — 200 = up
check_api "Discord" "https://discord.com/api/v10/gateway" "200"

if [[ -n "$ISSUES" ]]; then
	BODY=$(printf '%b' "$ISSUES")
	$NOTIFY --title "🔴 Lucky API Dependencies Down" --body "$BODY" --urgency alert || true
	log_warn "Discord alerted on external API issues."
else
	log_info "All external APIs healthy."
fi
log_info "External API check complete."
