#!/usr/bin/env bash
# Set one key in the agent-box SOPS secret (ADR 0037 decrypt/edit/encrypt pattern).
# `sops set` fails on this file (no creation rule), so this decrypts to tmpfs, replaces or
# appends KEY, re-encrypts to the file's own age recipient and checks the round trip before
# replacing the live file. The value is read from stdin and never printed.
#
# Usage (host, as luk-server):  read -rs V && printf '%s' "$V" | agent-box-secret-set.sh KEY; unset V
# Then `docker restart agent-box` to load it.
set -euo pipefail
umask 077
KEY=${1:?usage: agent-box-secret-set.sh KEY  (value on stdin)}
F=${AGENT_BOX_SECRET_FILE:-$HOME/homelab/secrets/agent-box.secrets.yaml.age}
[[ "$KEY" =~ ^[A-Z][A-Z0-9_]*$ ]] || { echo "ERROR: invalid key name"; exit 1; }
V=$(cat)
# Restricting the charset keeps the YAML line trivially safe to write and compare.
[[ "$V" =~ ^[A-Za-z0-9_.:-]+$ ]] || { echo "ERROR: empty value or unexpected characters"; exit 1; }

tmp=$(mktemp -d /dev/shm/agentbox-secret.XXXXXX)
trap 'rm -rf "$tmp"' EXIT

case "$KEY" in
    DISCORD_BOT_TOKEN)
        # Must belong to the agent's bot; the header goes in a file, not argv.
        printf 'Authorization: Bot %s\n' "$V" > "$tmp/hdr"
        code=$(curl -sS -o "$tmp/me.json" -w '%{http_code}' -H @"$tmp/hdr" https://discord.com/api/v10/users/@me)
        [[ "$code" == 200 ]] || { echo "ERROR: Discord rejected the token (HTTP $code)"; exit 1; }
        id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$tmp/me.json")
        want=${DISCORD_APP_ID:-1557913205966246039}
        [[ "$id" == "$want" ]] || { echo "ERROR: token belongs to bot $id, expected $want"; exit 1; }
        echo "token valid for bot $id" ;;
    DISCORD_OWNER_ID)
        [[ "$V" =~ ^[0-9]{15,22}$ ]] || { echo "ERROR: not a Discord user ID"; exit 1; } ;;
    AGENT_GITHUB_TOKEN)
        [[ "$V" == github_pat_* ]] || { echo "ERROR: not a fine-grained PAT"; exit 1; } ;;
esac

export SOPS_AGE_KEY_FILE=${SOPS_AGE_KEY_FILE:-$HOME/.config/sops/age/keys.txt}
S=(sops --config /dev/null --input-type yaml)
RECIP=$(grep -m1 -oE 'age1[a-z0-9]{50,}' "$F") || { echo "ERROR: no age recipient in $F"; exit 1; }
"${S[@]}" --output-type yaml -d "$F" > "$tmp/plain.yaml"
# Quoted, so a numeric ID stays a string.
K="$KEY" V="$V" awk '
    BEGIN { line = ENVIRON["K"] ": \"" ENVIRON["V"] "\"" }
    index($0, ENVIRON["K"] ":") == 1 { print line; done = 1; next }
    { print }
    END { if (!done) print line }' "$tmp/plain.yaml" > "$tmp/new.yaml"
"${S[@]}" --output-type yaml --age "$RECIP" -e "$tmp/new.yaml" > "$tmp/enc"

got=$("${S[@]}" --output-type dotenv -d "$tmp/enc" | awk -v k="$KEY=" 'index($0, k) == 1 { print substr($0, length(k) + 1) }')
[[ "$got" == "$V" ]] || { echo "ERROR: round-trip mismatch, live file untouched"; exit 1; }
old=$(grep -v "^$KEY:" "$tmp/plain.yaml" | sha256sum)
new=$("${S[@]}" --output-type yaml -d "$tmp/enc" | grep -v "^$KEY:" | sha256sum)
[[ "$old" == "$new" ]] || { echo "ERROR: other keys changed, live file untouched"; exit 1; }

cp -p "$F" "$F.bak-$(date +%F-%H%M%S)"
mv "$tmp/enc" "$F"
chmod 600 "$F"
echo "$KEY stored in $F (restart agent-box to load it)"
