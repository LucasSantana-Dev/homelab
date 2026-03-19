#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/github-api.sh"

REPOS_CSV="LucasSantana-Dev/homelab,LucasSantana-Dev/Lucky,LucasSantana-Dev/Craftvaria"
FAIL_ON_FAILURE="true"

usage() {
  cat <<'EOF'
Usage: main-ci-watchdog.sh [options]

Options:
  --repos-csv <csv>          Repositories list (owner/name,comma-separated)
  --fail-on-failure <bool>   true|false (default: true)
  --help                     Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repos-csv)
      REPOS_CSV="$2"
      shift 2
      ;;
    --fail-on-failure)
      FAIL_ON_FAILURE="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

require_gh_token

IFS=',' read -r -a repos <<< "$REPOS_CSV"

fail_count=0
warn_count=0

printf 'Main CI Watchdog at %s\n\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

for repo in "${repos[@]}"; do
  run_json="$(gh_retry gh run list --repo "$repo" --branch main --limit 1 --json workflowName,status,conclusion,url,headSha)"
  run_len="$(python3 -c 'import json,sys; print(len(json.load(sys.stdin)))' <<<"$run_json")"

  if [[ "$run_len" == "0" ]]; then
    echo "YELLOW $repo no main runs found"
    warn_count=$((warn_count + 1))
    continue
  fi

  IFS=$'\t' read -r workflow status conclusion url sha < <(
    python3 - <<'PY' "$run_json"
import json
import sys

data = json.loads(sys.argv[1])[0]
fields = [
    data.get("workflowName", ""),
    data.get("status", ""),
    data.get("conclusion", ""),
    data.get("url", ""),
    data.get("headSha", ""),
]
print("\t".join(fields))
PY
  )

  if [[ "$status" != "completed" ]]; then
    echo "YELLOW $repo workflow='$workflow' status=$status sha=${sha:0:7} url=$url"
    warn_count=$((warn_count + 1))
    continue
  fi

  if [[ "$conclusion" == "success" || "$conclusion" == "neutral" || "$conclusion" == "skipped" ]]; then
    echo "GREEN  $repo workflow='$workflow' conclusion=$conclusion sha=${sha:0:7} url=$url"
  else
    echo "RED    $repo workflow='$workflow' conclusion=$conclusion sha=${sha:0:7} url=$url"
    fail_count=$((fail_count + 1))
  fi
done

printf '\nSummary: green=%d yellow=%d red=%d\n' "$(( ${#repos[@]} - warn_count - fail_count ))" "$warn_count" "$fail_count"

if [[ "$FAIL_ON_FAILURE" == "true" && "$fail_count" -gt 0 ]]; then
  exit 1
fi

exit 0
