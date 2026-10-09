#!/usr/bin/env bash
# agent-pr-gate.sh: triage every open agent PR before the worker starts new work.
# Grades size, impact, value and security (agent_gate.py) and acts on the decision:
# close, needs-human, split, autofix (capped), wait, owner-review or auto-merge (only
# when auto_merge=true in agent-gate.json). PRs or issues another human touched are
# never acted on. AGENT_DRY_RUN=1 only reports.
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/agent-pr-gate-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting agent PR gate..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"
# shellcheck source=./agent-loop-lib.sh
source "$(dirname "$0")/agent-loop-lib.sh"

exec 9>/tmp/agent-worker.lock
flock -n 9 || { echo "worker run is active, exiting"; exit 0; }

if agent_paused; then
    echo "paused (~/agent-paused on agent-box, or agent-box unreachable), exiting"
    exit 0
fi

has_label() { jq -e --arg l "$1" 'any(.labels[]; .name == $l)' <<<"$PR_JSON" >/dev/null; }

comment_once() {  # repo pr sha body: one gate comment per head commit
    local repo="$1" n="$2" sha="$3" body="$4" marker qbody
    marker="<!-- agent-gate:$sha -->"
    if jq -e --arg m "$marker" 'any(.comments[]?; .body | contains($m))' <<<"$PR_JSON" >/dev/null; then
        return 0
    fi
    printf -v qbody '%q' "$body"$'\n\n'"$marker"
    try_act "gh pr comment $n --repo $repo --body $qbody"
}

for REPO in $AGENT_REPOS; do
    echo "--- $REPO"
    ensure_labels "$REPO"
    WORKDIR=$(cfg "$REPO" workdir)
    BASE=$(cfg "$REPO" base)
    FIX_MAX=$(cfg "$REPO" fix_attempts)
    STALE_DAYS=$(cfg "$REPO" stale_days)
    AUTOFIX_LEFT="${AGENT_MAX_AUTOFIX_PER_RUN:-1}"

    NUMS=$(open_agent_prs "$REPO" | jq -r '.[].number') || { echo "gh pr list failed"; continue; }
    for N in $NUMS; do
        [[ "$N" =~ ^[0-9]+$ ]] || continue
        PR_JSON=$(run_on_agent "gh pr view $N --repo $REPO --json number,author,commits,files,additions,deletions,closingIssuesReferences,statusCheckRollup,labels,comments,reviews,updatedAt,headRefName,headRefOid") || continue
        SHA=$(jq -r '.headRefOid' <<<"$PR_JSON")
        BRANCH=$(jq -r '.headRefName' <<<"$PR_JSON")
        if ! [[ "$SHA" =~ ^[0-9a-f]{40}$ && "$BRANCH" =~ ^[A-Za-z0-9._/-]+$ ]]; then
            echo "#$N: unexpected sha/branch, skipping"
            continue
        fi

        # Linked issue: closing reference, else the agent/issue-N branch name.
        ISSUE_N=$(jq -r '.closingIssuesReferences[0].number // empty' <<<"$PR_JSON")
        [[ -z "$ISSUE_N" && "$BRANCH" =~ ^agent/issue-([0-9]+)$ ]] && ISSUE_N="${BASH_REMATCH[1]}"
        ISSUE_JSON=null
        if [[ "$ISSUE_N" =~ ^[0-9]+$ ]]; then
            # A failed lookup is not "no linked issue": skip this run instead of closing.
            if ! ISSUE_JSON=$(run_on_agent "gh issue view $ISSUE_N --repo $REPO --json number,author,labels,comments") \
                || [[ -z "$ISSUE_JSON" ]]; then
                echo "#$N: could not load issue #$ISSUE_N, skipping this run"
                continue
            fi
        else
            ISSUE_N=""
        fi

        RES=$(jq -n --argjson pr "$PR_JSON" --argjson issue "${ISSUE_JSON:-null}" '{pr:$pr, issue:$issue}' | python3 "$GATE_PY" score --repo "$REPO")
        DECISION=$(jq -r '.decision' <<<"$RES")
        echo "#$N decision=$DECISION $(jq -c '.pillars' <<<"$RES")"

        [[ "$DECISION" == "halt" ]] && { echo "#$N: another human is involved, hands off"; continue; }

        # Stale-close only PRs the agent itself is stuck on, never ones waiting on the owner.
        UPDATED=$(jq -r '.updatedAt' <<<"$PR_JSON")
        if [[ "$DECISION" == "wait" || "$DECISION" == "autofix" ]] && ! has_label needs-human \
            && (( $(date +%s) - $(date -d "$UPDATED" +%s) > STALE_DAYS * 86400 )); then
            try_act "gh pr close $N --repo $REPO --comment 'agent-gate: closed after $STALE_DAYS days without progress. The issue is labelled agent-failed for a human look.'"
            [[ -n "$ISSUE_N" ]] && try_act "gh issue edit $ISSUE_N --repo $REPO --add-label agent-failed"
            continue
        fi

        TABLE=$(jq -r '"agent-gate: **\(.decision)**\n\n| pillar | grade |\n|---|---|\n" + ([.pillars | to_entries[] | "| \(.key) | \(.value) |"] | join("\n")) + "\n\n" + (.reasons | map("- " + .) | join("\n"))' <<<"$RES")

        case "$DECISION" in
            wait) ;;
            close)
                try_act "gh pr close $N --repo $REPO --comment $(printf '%q' "$TABLE")"
                [[ -n "$ISSUE_N" ]] && try_act "gh issue edit $ISSUE_N --repo $REPO --add-label agent-failed"
                ;;
            needs-human)
                if ! has_label needs-human; then
                    try_act "gh pr edit $N --repo $REPO --add-label needs-human"
                    notify --title "agent: #$N needs a human" --body "$REPO #$N: $(jq -r '.reasons | join("; ")' <<<"$RES")" --urgency alert
                fi
                comment_once "$REPO" "$N" "$SHA" "$TABLE"
                ;;
            split)
                has_label needs-split || try_act "gh pr edit $N --repo $REPO --add-label needs-split"
                comment_once "$REPO" "$N" "$SHA" "$TABLE"
                ;;
            autofix)
                has_label needs-human && continue
                TRIES=$(jq '[.labels[].name | select(startswith("agent-fix-"))] | length' <<<"$PR_JSON")
                if (( TRIES >= FIX_MAX )); then
                    try_act "gh pr edit $N --repo $REPO --add-label agent-failed --add-label needs-human"
                    comment_once "$REPO" "$N" "$SHA" "agent-gate: CI still red after $TRIES fix attempts. Handing over."
                    notify --title "agent: #$N needs a human" --body "$REPO #$N red after $TRIES fixes" --urgency warn
                    continue
                fi
                if [[ "$AGENT_DRY_RUN" != "1" ]] && ! workdir_clean "$WORKDIR"; then
                    echo "workdir $WORKDIR is dirty, skipping autofix of #$N"
                    notify --title "agent: dirty workdir" --body "$REPO $WORKDIR has uncommitted changes; autofix of #$N skipped" --urgency warn
                    continue
                fi
                (( AUTOFIX_LEFT > 0 )) || { echo "#$N: autofix deferred, per-run cap reached"; continue; }
                budget_take || continue
                # Count the attempt before running, so a crash cannot loop forever.
                # If the counter cannot be recorded, do not run (the cap would leak).
                if ! act "gh pr edit $N --repo $REPO --add-label agent-fix-$((TRIES + 1))"; then
                    echo "#$N: could not record fix attempt, skipping"
                    continue
                fi
                AUTOFIX_LEFT=$((AUTOFIX_LEFT - 1))
                PROMPT="You are on branch $BRANCH of $REPO, PR #$N. Its CI is failing. Read the failing checks with \`gh pr checks $N --repo $REPO\` and their logs, fix the root cause (not the test), run the checks locally, commit (no AI attribution) and push to $BRANCH. Do not touch unrelated files. Never force-push or merge. Run git and gh as single plain commands from the repo root: no cd, no && or ; chains, no \$(...); write the message with the Write tool to .git/agent-commit-msg and use git commit -F .git/agent-commit-msg."
                if act "cd $WORKDIR && git fetch -q origin && git switch -q -C $BRANCH origin/$BRANCH"; then
                    act "$(claude_cmd "$REPO" "$WORKDIR" "$PROMPT")" || echo "claude exited non-zero"
                else
                    echo "git checkout failed for $BRANCH"
                fi
                try_act "cd $WORKDIR && git switch -q --detach origin/$BASE"
                ;;
            owner-review)
                comment_once "$REPO" "$N" "$SHA" "$TABLE"
                ;;
            auto-merge)
                comment_once "$REPO" "$N" "$SHA" "$TABLE"
                if act "gh pr merge $N --repo $REPO --auto --squash --match-head-commit $SHA"; then
                    notify --title "agent: auto-merge queued #$N" --body "$REPO #$N, 4 green pillars" --urgency info
                else
                    echo "#$N: gh pr merge --auto failed"
                fi
                ;;
        esac
    done
done

echo "[$(date)] agent PR gate complete."
