#!/usr/bin/env bash
# check_deploy_drift.sh — does the deployed compose match this repo? (#269)
#
# Born from a real failure: fixing the #264 outage meant editing compose on the
# host with sed rather than copying the corrected file, because the host copy
# carried feature flags and secrets that were never committed. A `git pull`
# there is a destructive command and nothing says so.
#
# Compares STRUCTURE, never values: every `KEY: value` and `KEY=value` is
# reduced to `KEY: <set>` before diffing, so no secret can reach stdout even
# when the host file is full of them.
#
# Usage:  scripts/check_deploy_drift.sh [ssh-host] [remote-dir]
# Run from the repo root.
# Exit:   0 in sync · 1 drifted · 2 could not compare
set -uo pipefail

SSH_HOST="${1:-homelab}"
REMOTE_DIR="${2:-/home/luk-server/homelab}"
# Every deployable file, not a hardcoded few. The three-file list this started
# with reported "in sync" while compose/brain-mcp.yml had gained a whole
# service the host never received (#269).
FILES=$(ls compose/*.yml docker-compose.yml config/caddy/Caddyfile 2>/dev/null)

# Redact values, keep shape. Also drops comments and blank lines so a reworded
# comment is not reported as drift.
redact() {
  sed -E \
    -e 's/^([[:space:]]*[A-Za-z_][A-Za-z0-9_]*):[[:space:]]+.+$/\1: <set>/' \
    -e 's/^([[:space:]]*-[[:space:]]*[A-Za-z_][A-Za-z0-9_]*)=.+$/\1=<set>/' \
    -e 's/[[:space:]]+$//' \
    | grep -vE '^[[:space:]]*(#|$)'
}

command -v ssh >/dev/null 2>&1 || { echo "ssh not found"; exit 2; }

if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$SSH_HOST" true 2>/dev/null; then
  echo "ERROR could not reach $SSH_HOST"
  exit 2
fi

drifted=0
for f in $FILES; do
  if [ ! -f "$f" ]; then
    echo "SKIP  $f (not in this repo)"
    continue
  fi

  # A file the host does not have is drift, not an error: the repo ships config
  # production never received, which is exactly what this script looks for.
  # Reachability was already proven above, so a failure here means absent.
  if ! remote=$(ssh -o BatchMode=yes -o ConnectTimeout=10 "$SSH_HOST" \
        "test -f '$REMOTE_DIR/$f' && cat '$REMOTE_DIR/$f'" 2>/dev/null); then
    drifted=1
    echo "ABSENT $f (never deployed to $SSH_HOST)"
    continue
  fi

  if diff -q <(printf '%s\n' "$remote" | redact) <(redact < "$f") >/dev/null; then
    echo "OK    $f"
    continue
  fi

  drifted=1
  echo "DRIFT $f"
  echo "      < deployed on $SSH_HOST   > this repo"
  diff <(printf '%s\n' "$remote" | redact) <(redact < "$f") | sed 's/^/      /'
done

if [ "$drifted" -ne 0 ]; then
  cat <<'EOF'

The deployed configuration differs from this repo.

Do NOT `git pull` on the host to fix it: the host copy is the running state and
a pull would discard whatever is only there. Reconcile toward the repo
deliberately, moving secrets to a secret store and non-secret config into the
committed file. See issue #269.
EOF
  exit 1
fi

echo "In sync."
