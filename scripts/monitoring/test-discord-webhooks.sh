#!/bin/bash
# Validate every DISCORD_*WEBHOOK* URL in .env by issuing a GET (no message sent).
# A healthy webhook returns HTTP 200 with JSON metadata; 404 means the webhook
# was deleted in Discord and needs to be regenerated on the Discord side.
set -euo pipefail

ENV_FILE="${ENV_FILE:-$(dirname "$0")/../../.env}"
[ -f "$ENV_FILE" ] || { echo "ENV_FILE not found: $ENV_FILE" >&2; exit 2; }

fail=0
while IFS='=' read -r key url; do
  [ -z "$key" ] && continue
  case "$key" in *DISCORD*|*WEBHOOK*) ;; *) continue;; esac
  [ -z "$url" ] && { printf '%-40s MISSING\n' "$key"; fail=1; continue; }
  tmp=$(mktemp)
  code=$(curl -s -o "$tmp" -w "%{http_code}" -m 8 "$url" || echo 000)
  if [ "$code" = "200" ]; then
    name=$(python3 -c "import json,sys;d=json.load(open('$tmp'));print(d.get('name','?'),'@',d.get('channel_id','?'))" 2>/dev/null || echo "?")
    printf '%-40s OK   %s\n' "$key" "$name"
  else
    printf '%-40s FAIL HTTP %s\n' "$key" "$code"
    fail=1
  fi
  rm -f "$tmp"
done < <(grep -E "^[A-Z_]*DISCORD[A-Z_]*=" "$ENV_FILE" 2>/dev/null)

exit "$fail"
