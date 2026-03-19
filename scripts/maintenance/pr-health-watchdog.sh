#!/usr/bin/env bash

set -euo pipefail

REPOS_CSV="${REPOS_CSV:-LucasSantana-Dev/homelab,LucasSantana-Dev/Lucky,LucasSantana-Dev/Craftvaria}"
MAX_OPEN_PRS="${MAX_OPEN_PRS:-30}"
FAIL_ON_RED="${FAIL_ON_RED:-true}"

usage() {
  cat <<'EOF'
Usage: pr-health-watchdog.sh [options]

Options:
  --repos-csv VALUE      Comma-separated owner/repo list
  --max-open-prs N       Max open PRs to inspect per repo (default: 30)
  --fail-on-red BOOL     Exit non-zero on failing checks (default: true)
  -h, --help             Show help

Environment:
  GH_TOKEN               Required for GitHub API/CLI access
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repos-csv)
      REPOS_CSV="$2"
      shift 2
      ;;
    --max-open-prs)
      MAX_OPEN_PRS="$2"
      shift 2
      ;;
    --fail-on-red)
      FAIL_ON_RED="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "GH_TOKEN is required" >&2
  exit 1
fi

IFS=',' read -r -a repos <<<"${REPOS_CSV}"

overall_failures=0
overall_open_prs=0

echo "PR Health Watchdog"
echo "Timestamp: $(date --iso-8601=seconds)"
echo "Repos: ${REPOS_CSV}"
echo

for repo in "${repos[@]}"; do
  repo="$(echo "${repo}" | xargs)"
  if [[ -z "${repo}" ]]; then
    continue
  fi

  echo "## ${repo}"

  pr_list="$(gh pr list --repo "${repo}" --state open --limit "${MAX_OPEN_PRS}" --json number,title,url)"
  pr_count="$(python3 -c 'import json,sys; print(len(json.load(sys.stdin)))' <<<"${pr_list}")"
  overall_open_prs=$((overall_open_prs + pr_count))

  if [[ "${pr_count}" -eq 0 ]]; then
    echo "- Open PRs: 0"
    echo
    continue
  fi

  echo "- Open PRs: ${pr_count}"

  while IFS='|' read -r pr_number pr_title pr_url; do
    if [[ -z "${pr_number}" ]]; then
      continue
    fi

    checks_json="$(gh pr view "${pr_number}" --repo "${repo}" --json statusCheckRollup)"

    verdict="$(python3 - <<'PY' "${checks_json}"
import json
import sys

data = json.loads(sys.argv[1])
checks = data.get("statusCheckRollup", [])

bad_states = {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"}
pending_states = {"PENDING", "QUEUED", "IN_PROGRESS", "EXPECTED"}

bad = 0
pending = 0
for item in checks:
    t = item.get("__typename")
    if t == "CheckRun":
        conclusion = (item.get("conclusion") or "").upper()
        status = (item.get("status") or "").upper()
        if conclusion in bad_states:
            bad += 1
        elif status in pending_states:
            pending += 1
    elif t == "StatusContext":
        state = (item.get("state") or "").upper()
        if state in bad_states:
            bad += 1
        elif state in pending_states:
            pending += 1

if bad > 0:
    print("RED")
elif pending > 0:
    print("YELLOW")
else:
    print("GREEN")
PY
)"

    if [[ "${verdict}" == "RED" ]]; then
      overall_failures=$((overall_failures + 1))
      echo "  - RED #${pr_number}: ${pr_title} (${pr_url})"
    elif [[ "${verdict}" == "YELLOW" ]]; then
      echo "  - YELLOW #${pr_number}: ${pr_title} (${pr_url})"
    else
      echo "  - GREEN #${pr_number}: ${pr_title} (${pr_url})"
    fi
  done < <(python3 - <<'PY' "${pr_list}"
import json
import sys

for pr in json.loads(sys.argv[1]):
    print(f"{pr['number']}|{pr['title']}|{pr['url']}")
PY
)

  echo
done

echo "Summary: open_prs=${overall_open_prs} red_prs=${overall_failures}"

if [[ "${FAIL_ON_RED}" == "true" && "${overall_failures}" -gt 0 ]]; then
  exit 2
fi

exit 0
