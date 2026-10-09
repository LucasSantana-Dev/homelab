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
# REST, not `gh pr view`: that strips the [bot] suffix and has no is_bot, so
# hermes's own earlier comment (github-actions) counted as human and blocked
# every later review on the PR. user.type tells bots from people.
# Each gh call before the review gets 60s, so a slow API skips the run instead
# of eating the ssh budget below.
HUMAN_IDS=$(timeout 60 gh api --paginate "repos/$REPO/issues/$PR_NUMBER/comments" \
  --jq '.[] | select(.user.type != "Bot") | .id') \
  || { log "WARN: gh failed checking comments, skipping review"; exit 0; }
HUMAN_COMMENTS=$(grep -c . <<<"$HUMAN_IDS" || true)

if [ "$HUMAN_COMMENTS" -gt 0 ]; then
    log "Skipping: $HUMAN_COMMENTS human comment(s) already present — CLAUDE.md hard rule"
    exit 0
fi

# Guard: skip if hermes already reviewed this exact commit.
# Use the PR HEAD SHA (what we actually review below), NOT `git rev-parse HEAD` —
# on pull_request events the checkout is the ephemeral refs/pull/N/merge commit,
# so its SHA changes with the base and never matches the reviewed head (#310).
HEAD_SHA=$(timeout 60 gh pr view "$PR_NUMBER" --repo "$REPO" --json headRefOid --jq '.headRefOid' 2>/dev/null) \
  || { log "WARN: gh failed resolving PR head SHA — skipping review"; exit 0; }
if [ -z "$HEAD_SHA" ]; then log "WARN: empty PR head SHA — skipping review"; exit 0; fi
# The posted comment stores only the 8-char short SHA (see printf below), so the
# dedup check must match that same form — comparing the full 40-char SHA would
# never hit and duplicates would be posted (#310).
SHORT_SHA="${HEAD_SHA:0:8}"
# Paginated REST (gh pr view caps the comment list), bot comments only.
EXISTING_REVIEW=$(timeout 60 gh api --paginate "repos/$REPO/issues/$PR_NUMBER/comments" \
  --jq ".[] | select(.user.type == \"Bot\" and (.body | startswith(\"[hermes] code review ($SHORT_SHA)\"))) | .id") \
  || { log "WARN: gh failed checking existing reviews, skipping review"; exit 0; }
if [ -n "$EXISTING_REVIEW" ]; then
    log "Already reviewed at $HEAD_SHA — skipping"
    exit 0
fi

# Fetch PR branch in agent-box workspace and run review
log "Fetching PR branch and running review on agent-box..."
REVIEW_STATUS=ok
# agent-box authorizes only the dedicated key (the one the `agent-box` alias uses),
# not the default ~/.ssh/id_* keys. Host key checking stays strict.
# The outer cap covers fetch and cleanup too, so a hung git or network still
# leaves time to post the fallback inside the 10-minute job. Budgeted from
# START_TS (520s, not 540: checkout runs before this script starts), so slow gh
# calls above shrink it instead of eating the posting window.
SSH_CAP=$(( 520 - ($(date +%s) - START_TS) ))
[ "$SSH_CAP" -ge 30 ] || SSH_CAP=30
if ! REVIEW=$(timeout "$SSH_CAP" ssh -p 2222 -o BatchMode=yes -o ConnectTimeout=10 \
    -i /home/luk-server/.ssh/agent-box -o IdentitiesOnly=yes \
    agent@localhost \
    "source /etc/profile.d/agent-env.sh 2>/dev/null
     set -e
     cd /workspace/homelab
     git fetch -q origin '+refs/pull/$PR_NUMBER/head:hermes-pr-$PR_NUMBER'
     git checkout -q hermes-pr-$PR_NUMBER
     # Subscription login, like claude_cmd: the exported API key is invalid and
     # would take precedence. A failed review still restores main below.
     rc=0
     # 420s, not 600: the job has timeout-minutes 10, and the fallback comment
     # must still post before GitHub kills the runner.
     REVIEW_OUT=\$(timeout 420 env -u ANTHROPIC_API_KEY -u CLAUDE_API_KEY claude --print \
       'Review the current branch (hermes-pr-$PR_NUMBER) against $BASE_REF. What are the top 3-5 issues, bugs, or improvements? Format as markdown bullets. Include [severity: high|medium|low] for each. If nothing notable, say so in one line.' \
       2>&1) || rc=\$?
     git checkout -q main
     git branch -q -D hermes-pr-$PR_NUMBER || true
     printf '%s' \"\$REVIEW_OUT\"
     exit \$rc" 2>&1); then
    REVIEW_STATUS=error
    # Keep the real error in the log: the PR comment only gets the fallback.
    log "agent-box review failed: $(tail -c 1000 <<<"$REVIEW")"
    REVIEW="hermes: review unavailable (agent-box unreachable or error). Check $LOG_FILE."
fi

log "Review complete (${#REVIEW} chars)"
# GitHub rejects comment bodies over 65536 chars; keep room for the wrapper.
if [ "${#REVIEW}" -gt 60000 ]; then
    REVIEW="${REVIEW:0:60000}

(truncated at 60000 chars)"
fi

# Post comment
BODY="$(printf '[hermes] code review (%s)\n\n%s\n\n---\n*Advisory only — not a blocking gate.*' \
  "$SHORT_SHA" "$REVIEW")"

# A failed post still records `error` in the state file, then fails the job.
COMMENT_RC=0
gh pr comment "$PR_NUMBER" --repo "$REPO" --body "$BODY" || COMMENT_RC=$?
if [ "$COMMENT_RC" -eq 0 ]; then
    log "Comment posted to PR #$PR_NUMBER"
else
    REVIEW_STATUS=error
    log "ERROR: posting comment to PR #$PR_NUMBER failed (rc=$COMMENT_RC)"
fi

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
# The counter means reviews posted, so a failed post does not count.
if [ "$COMMENT_RC" -ne 0 ]; then
    log "Skipping Prometheus metrics: comment was not posted"
elif [ -d "$PROM_DIR" ] && [ -w "$PROM_DIR" ]; then
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

# JSON state for homelab-manager /hermes endpoint. Locked like the Prometheus
# block: reviews of different PRs can run at once and lose an increment (#310).
(
flock 9
python3 -c "
import json, os, time
state_file = '$STATE_DIR/hermes-state.json'
try:
    state = json.load(open(state_file))
except Exception:
    state = {}
state['pr_review'] = {
    'last_run': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime($END_TS)),
    'status': '$REVIEW_STATUS',
    'last_pr': $PR_NUMBER,
    'duration_s': $DURATION,
    'total': state.get('pr_review', {}).get('total', 0) + 1,
}
# Write then rename, so a crash mid-write never leaves truncated JSON.
with open(state_file + '.tmp', 'w') as f:
    json.dump(state, f, indent=2)
os.replace(state_file + '.tmp', state_file)
"
) 9>"$STATE_DIR/hermes-state.lock" || log "WARN: could not write $STATE_DIR/hermes-state.json"

exit "$COMMENT_RC"
