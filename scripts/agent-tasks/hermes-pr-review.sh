#!/usr/bin/env bash
# hermes-pr-review.sh — run Claude code review on a PR via agent-box, post as PR comment.
# Called from .github/workflows/hermes-review.yml running on the homelab self-hosted runner.
#
# Usage: hermes-pr-review.sh <pr_number> <base_ref> <repo>
#   GH_TOKEN must be set (passed by GHA as secrets.GITHUB_TOKEN with pull-requests:write)
set -euo pipefail

PR_NUMBER="${1:?PR_NUMBER required}"
[[ "$PR_NUMBER" =~ ^[0-9]+$ ]] || { echo "PR_NUMBER must be numeric, got: $PR_NUMBER" >&2; exit 2; }
BASE_REF="${2:?BASE_REF required}"
[[ "$BASE_REF" =~ ^[A-Za-z0-9._/-]+$ ]] || { echo "BASE_REF contains invalid characters, got: $BASE_REF" >&2; exit 2; }
[[ "$BASE_REF" != *".."* ]] || { echo "BASE_REF must not contain '..', got: $BASE_REF" >&2; exit 2; }
REPO="${3:?REPO required}"
[[ "$REPO" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]] || { echo "REPO must be in owner/repo format, got: $REPO" >&2; exit 2; }

LOG_FILE="/home/luk-server/agent-logs/hermes-pr-review-${PR_NUMBER}-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee "$LOG_FILE") 2>&1

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S')] $*"; }

START_TS=$(date +%s)
log "hermes PR review — PR #$PR_NUMBER base=$BASE_REF repo=$REPO"

# Guard: skip if any human (non-bot) has already commented — CLAUDE.md hard rule
HUMAN_COMMENTS=$(gh pr view "$PR_NUMBER" --repo "$REPO" --json comments \
  --jq '[.comments[] | select(
    .author.login != "github-actions[bot]" and
    .author.login != "dependabot[bot]" and
    .author.login != "renovate[bot]" and
    .author.login != "coderabbitai[bot]" and
    .author.login != "greptile-apps[bot]" and
    (.author.is_bot // false) == false
  )] | length' 2>&1) || { log "WARN: gh failed checking comments — skipping review"; exit 0; }

if [ "$HUMAN_COMMENTS" -gt 0 ]; then
    log "Skipping: $HUMAN_COMMENTS human comment(s) already present — CLAUDE.md hard rule"
    exit 0
fi

# Guard: skip if hermes already reviewed this exact commit.
# Use the PR HEAD SHA (what we actually review below), NOT `git rev-parse HEAD` —
# on pull_request events the checkout is the ephemeral refs/pull/N/merge commit,
# so its SHA changes with the base and never matches the reviewed head (#310).
HEAD_SHA=$(gh pr view "$PR_NUMBER" --repo "$REPO" --json headRefOid --jq '.headRefOid' 2>/dev/null) \
  || { log "WARN: gh failed resolving PR head SHA — skipping review"; exit 0; }
if [ -z "$HEAD_SHA" ]; then log "WARN: empty PR head SHA — skipping review"; exit 0; fi
# The posted comment stores only the 8-char short SHA (see printf below), so the
# dedup check must match that same form — comparing the full 40-char SHA would
# never hit and duplicates would be posted (#310).
SHORT_SHA="${HEAD_SHA:0:8}"
EXISTING_REVIEW=$(gh pr view "$PR_NUMBER" --repo "$REPO" --json comments \
  --jq ".comments[] | select(.body | startswith(\"[hermes] code review ($SHORT_SHA)\"))" \
  2>&1) || { log "WARN: gh failed checking existing reviews — skipping review"; exit 0; }
if [ -n "$EXISTING_REVIEW" ]; then
    log "Already reviewed at $HEAD_SHA — skipping"
    exit 0
fi

# Fetch PR branch in agent-box workspace and run review
log "Fetching PR branch and running review on agent-box..."
REVIEW=$(ssh -p 2222 -o BatchMode=yes -o ConnectTimeout=10 \
    agent@localhost \
    "source /etc/profile.d/agent-env.sh 2>/dev/null
     set -e
     set -o pipefail   # else the timeout-claude-tail pipeline masks a timed-out review as success
     cd /workspace/homelab
     git fetch origin '+refs/pull/$PR_NUMBER/head:hermes-pr-$PR_NUMBER' 2>&1
     git checkout hermes-pr-$PR_NUMBER 2>&1
     REVIEW_OUT=\$(timeout 600 claude --print \
       'Review the current branch (hermes-pr-$PR_NUMBER) against $BASE_REF. What are the top 3-5 issues, bugs, or improvements? Format as markdown bullets. Include [severity: high|medium|low] for each. If nothing notable, say so in one line.' \
       2>&1 | tail -n +1)
     git checkout main 2>&1
     git branch -D hermes-pr-$PR_NUMBER 2>&1 || true
     printf '%s' \"\$REVIEW_OUT\"" 2>&1) \
  || REVIEW="hermes: review unavailable — agent-box unreachable or error. Check $LOG_FILE."

log "Review complete (${#REVIEW} chars)"

# Post comment
BODY="$(printf '[hermes] code review (%s)\n\n%s\n\n---\n*Advisory only — not a blocking gate.*' \
  "$SHORT_SHA" "$REVIEW")"

gh pr comment "$PR_NUMBER" --repo "$REPO" --body "$BODY"
log "Comment posted to PR #$PR_NUMBER"

# Write metrics for node-exporter textfile collector and homelab-manager state
END_TS=$(date +%s)
DURATION=$((END_TS - START_TS))
STATE_DIR="/home/luk-server/agent-logs"
PROM_DIR="/var/lib/node_exporter/textfile"

# Prometheus textfile metrics (best-effort telemetry). Guard on writability, not
# just existence: the collector dir can exist but be unwritable by the runner
# user, which made the `9>lock` redirect fail with "Permission denied" and — under
# `set -e` — failed the whole review job AFTER the review had already posted (#382).
# A non-writable dir is now a logged skip, never a job failure.
if [ -d "$PROM_DIR" ] && [ -w "$PROM_DIR" ]; then
    # Hold the lock across the ENTIRE read-modify-write — the previous version
    # only locked the read, so concurrent reviews could both read N and write
    # N+1, losing an increment (#310). fd 9 keeps the lock for the subshell.
    (
        flock 9
        # `|| echo 0`: grep exits non-zero on first run / missing counter line,
        # which would abort this subshell under `set -o pipefail` (#310).
        PREV_COUNT=$(grep '^hermes_pr_reviews_total ' "$PROM_DIR/hermes.prom" 2>/dev/null | awk '{print $2}' || echo 0)
        NEW_COUNT=$(( ${PREV_COUNT:-0} + 1 ))
        cat > "$PROM_DIR/hermes.prom.tmp" <<PROM
# HELP hermes_pr_reviews_total Total PR reviews posted by hermes
# TYPE hermes_pr_reviews_total counter
hermes_pr_reviews_total $NEW_COUNT
# HELP hermes_pr_review_last_timestamp_seconds Unix timestamp of last hermes PR review
# TYPE hermes_pr_review_last_timestamp_seconds gauge
hermes_pr_review_last_timestamp_seconds $END_TS
# HELP hermes_pr_review_last_duration_seconds Duration of last hermes PR review in seconds
# TYPE hermes_pr_review_last_duration_seconds gauge
hermes_pr_review_last_duration_seconds $DURATION
# HELP hermes_pr_review_last_pr_number PR number of last hermes review
# TYPE hermes_pr_review_last_pr_number gauge
hermes_pr_review_last_pr_number $PR_NUMBER
PROM
        mv "$PROM_DIR/hermes.prom.tmp" "$PROM_DIR/hermes.prom"
    ) 9>"$PROM_DIR/hermes.prom.lock"
    log "Prometheus metrics written to $PROM_DIR/hermes.prom"
else
    log "Skipping Prometheus metrics: $PROM_DIR missing or not writable by $(id -un) (#382)"
fi

# JSON state for homelab-manager /hermes endpoint
python3 -c "
import json, os, time
state_file = '$STATE_DIR/hermes-state.json'
try:
    state = json.load(open(state_file))
except Exception:
    state = {}
state['pr_review'] = {
    'last_run': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime($END_TS)),
    'status': 'ok',
    'last_pr': $PR_NUMBER,
    'duration_s': $DURATION,
    'total': state.get('pr_review', {}).get('total', 0) + 1,
}
json.dump(state, open(state_file, 'w'), indent=2)
" 2>/dev/null || true
