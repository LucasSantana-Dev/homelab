#!/usr/bin/env bash
# check_deploy_drift.sh — does the deployed configuration match this repo? (#269)
#
# Born from a real failure: fixing the #264 outage meant editing compose on the
# host with sed rather than copying the corrected file, because the host copy
# carried feature flags and secrets that were never committed. A `git pull`
# there is a destructive command and nothing says so.
#
# Compares STRUCTURE, never values, for the file types where that is reliable.
# See "Redaction" below for the types where it is not, and what happens instead.
#
# Usage:  scripts/check_deploy_drift.sh [ssh-host] [remote-dir]
# Run from the repo root.
# Exit:   0 in sync · 1 drifted · 2 could not compare
set -uo pipefail

SSH_HOST="${1:-homelab}"
REMOTE_DIR="${2:-/home/luk-server/homelab}"

command -v ssh >/dev/null 2>&1 || { echo "ssh not found"; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 not found"; exit 2; }

# The file list is DERIVED, never hand-maintained. Two hardcoded lists have now
# each hidden a real drift: the original three missed compose/brain-mcp.yml
# gaining a whole service, and its replacement missed
# config/prometheus/prometheus.yml, a mounted config that had also drifted.
#
# Anything a container reads is deployable, so the manifests are the source:
# every compose file, plus every host path they bind-mount that exists here.
# Mounted directories expand to their files.
list_deployable_files() {
  python3 - <<'PY'
import glob, os, yaml

manifests = sorted(glob.glob('compose/*.yml')) + \
            [f for f in ('docker-compose.yml',) if os.path.isfile(f)]

mounted = set()
for manifest in manifests:
    base = os.path.dirname(manifest) or '.'
    try:
        doc = yaml.safe_load(open(manifest)) or {}
    except yaml.YAMLError:
        continue  # a malformed manifest is the yaml linter's problem, not ours
    for service in (doc.get('services') or {}).values():
        for volume in (service.get('volumes') or []):
            source = volume.split(':')[0] if isinstance(volume, str) else (volume.get('source') or '')
            if not source.startswith('.'):
                continue  # named volume or absolute host path: not ours to track
            path = os.path.normpath(os.path.join(base, source))
            if os.path.isfile(path):
                mounted.add(path)
            elif os.path.isdir(path):
                for root, _, names in os.walk(path):
                    mounted.update(os.path.join(root, n) for n in names)

for path in sorted(set(manifests) | mounted):
    print(path)
PY
}

# Redaction: every `KEY: value` and `KEY=value` becomes `KEY: <set>`, so no
# secret reaches stdout even when the host file is full of them. Comments and
# blank lines are dropped so a reworded comment is not reported as drift.
redact() {
  sed -E \
    -e 's/^([[:space:]]*[A-Za-z_][A-Za-z0-9_]*):[[:space:]]+.+$/\1: <set>/' \
    -e 's/^([[:space:]]*-[[:space:]]*[A-Za-z0-9_]+)=.+$/\1=<set>/' \
    -e 's/[[:space:]]+$//' \
    | grep -vE '^[[:space:]]*(#|$)'
}

# That redaction only understands `KEY: value` on one line, so the diff body is
# printed only where that shape is the whole file. Two things break it:
#
#   - Files we do not author: authorized_keys, shell scripts, JSON. A secret
#     there does not sit to the right of a colon.
#   - YAML block scalars (`key: |`). The value lives on the FOLLOWING lines,
#     which the regex never sees. config/alertmanager/alertmanager.yml and
#     config/prometheus/alerts.yml both use them today, and an alertmanager
#     config is exactly where a webhook URL or token lives.
#
# Both are still COMPARED. Only the body is withheld.
diff_is_safe_to_print() {
  case "$1" in
    compose/*.yml|docker-compose.yml|*/Caddyfile) ;;
    *) return 1 ;;
  esac
  ! grep -qE ':[[:space:]]*[|>][-+0-9]*[[:space:]]*$' "$1"
}

# Bash command substitution strips NUL bytes and trailing newlines, so a binary
# mount read through `$(ssh ... cat)` arrives corrupted and reports drift on
# every run. Two are mounted today (a .png and a .gz). base64 survives the
# round trip intact.
fetch_remote() {
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$SSH_HOST" \
    "base64 < '$REMOTE_DIR/$1'" 2>/dev/null | base64 -d 2>/dev/null
}

is_binary() {
  LC_ALL=C grep -qI . "$1" 2>/dev/null && return 1
  return 0
}

if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$SSH_HOST" true 2>/dev/null; then
  echo "ERROR could not reach $SSH_HOST"
  exit 2
fi

TMP_REMOTE=$(mktemp); TMP_A=$(mktemp); TMP_B=$(mktemp)
trap 'rm -f "$TMP_REMOTE" "$TMP_A" "$TMP_B"' EXIT

FILES=$(list_deployable_files)
[ -n "$FILES" ] || { echo "ERROR no deployable files found; run from the repo root"; exit 2; }

drifted=0
unreadable=0
checked=0

for f in $FILES; do
  checked=$((checked + 1))

  # `test -f` is asked separately from `cat` so the two failures stay distinct:
  # a file the host never received is drift (the repo ships config production
  # does not have), while a file that exists but cannot be read is a broken
  # comparison and must not be reported as either in sync or drifted.
  if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$SSH_HOST" \
        "test -f '$REMOTE_DIR/$f'" 2>/dev/null; then
    drifted=1
    echo "ABSENT $f (never deployed to $SSH_HOST)"
    continue
  fi

  if ! fetch_remote "$f" > "$TMP_REMOTE"; then
    unreadable=1
    echo "ERROR $f exists on $SSH_HOST but could not be read (permissions?)"
    continue
  fi

  # Binary mounts carry no key/value shape to redact and no readable diff, so
  # they are compared byte for byte and reported without a body.
  if is_binary "$f" || is_binary "$TMP_REMOTE"; then
    if cmp -s "$TMP_REMOTE" "$f"; then
      echo "OK     $f"
    else
      drifted=1
      echo "DRIFT  $f (binary differs)"
    fi
    continue
  fi

  redact < "$TMP_REMOTE" > "$TMP_A"
  redact < "$f" > "$TMP_B"

  if cmp -s "$TMP_A" "$TMP_B"; then
    echo "OK     $f"
    continue
  fi

  drifted=1
  if diff_is_safe_to_print "$f"; then
    echo "DRIFT  $f"
    echo "       < deployed on $SSH_HOST   > this repo"
    diff "$TMP_A" "$TMP_B" | sed 's/^/       /'
  else
    lines=$(diff "$TMP_A" "$TMP_B" | grep -cE '^[<>]')
    echo "DRIFT  $f ($lines lines differ; body withheld, redaction is unreliable for this file)"
  fi
done

echo
echo "$checked files checked."

if [ "$unreadable" -ne 0 ]; then
  echo "At least one file could not be read, so this run proves nothing about it."
  exit 2
fi

if [ "$drifted" -ne 0 ]; then
  cat <<'EOF'

The deployed configuration differs from this repo.

Do NOT `git pull` on the host to fix it: the host copy is the running state and
a pull would discard whatever is only there. Reconcile toward the repo
deliberately, moving secrets to a secret store and non-secret config into the
committed file.

Check the direction before acting. The repo being AHEAD is the dangerous case:
config/caddy/Caddyfile currently routes to a port whose service was never
deployed, so copying it to the host would 502 that service. See issue #269.
EOF
  exit 1
fi

echo "In sync."
