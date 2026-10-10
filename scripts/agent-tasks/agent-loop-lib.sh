#!/usr/bin/env bash
# Shared helpers for agent-pr-gate.sh and agent-worker.sh (the autonomous dev loop).
# Source after common.sh. Policy and thresholds: config/agent-box/agent-gate.json.

AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATE_PY="$AGENT_DIR/agent_gate.py"
AGENT_REPOS="${AGENT_REPOS:-LucasSantana-Dev/Lucky}"
AGENT_DRY_RUN="${AGENT_DRY_RUN:-0}"
AGENT_MAX_RUNS_PER_DAY="${AGENT_MAX_RUNS_PER_DAY:-6}"
AGENT_STATE_DIR="${AGENT_STATE_DIR:-/home/luk-server/agent-state}"
# New work branches look like the owner's own: fix/issue-N. The legacy agent/ prefix and
# the `agent` label still mark PRs opened before the switch, so those keep being tracked.
export AGENT_BRANCH_PREFIX="fix/issue-"

cfg() { python3 "$GATE_PY" get --repo "$1" --key "$2"; }

# Pause switch lives inside agent-box so the Discord channel session can flip it.
# Fail closed: anything but an explicit "running" (ssh down, etc.) counts as paused.
agent_paused() {
    [[ "$(run_on_agent "test -e ~/agent-paused && echo paused || echo running")" != "running" ]]
}

# Run a command on agent-box, or only print it when AGENT_DRY_RUN=1.
act() {
    if [[ "$AGENT_DRY_RUN" == "1" ]]; then
        echo "DRY-RUN: $1"
    else
        run_on_agent "$1"
    fi
}

# Best-effort write (labels, comments): a failure is logged, never aborts the run.
try_act() { act "$1" || echo "WARN: failed: $1"; }

notify() {
    if [[ "$AGENT_DRY_RUN" == "1" ]]; then
        echo "DRY-RUN notify: $*"
    else
        $NOTIFY "$@"
    fi
}

# Daily claude -p budget shared by worker and gate autofix. Returns 1 when spent.
# Serialized by the flock both scripts take.
budget_take() {
    mkdir -p "$AGENT_STATE_DIR"
    local f used
    f="$AGENT_STATE_DIR/runs-$(date +%Y%m%d)"
    used=$(cat "$f" 2>/dev/null || echo 0)
    if (( used >= AGENT_MAX_RUNS_PER_DAY )); then
        echo "daily budget spent ($used/$AGENT_MAX_RUNS_PER_DAY)"
        return 1
    fi
    [[ "$AGENT_DRY_RUN" == "1" ]] || echo $((used + 1)) > "$f"
}

# Headless claude on the official binary with the Max OAuth login: every API or
# alternate-provider env var is dropped so a run never bills the API by accident.
# Permissions are pinned per run (mode + allow/deny lists from agent-gate.json), so
# a later change to the box's global settings cannot widen what the worker may do.
# The prompt goes in on stdin so the variadic tool flags cannot swallow it.
# Push is allowed only as the exact `git push [-u] origin <branch>` (no globs, so no
# refspec, --force or --delete variants); a branch outside fix/ or agent/ gets no run at all.
claude_cmd() {
    local repo="$1" workdir="$2" prompt="$3" branch="$4" qprompt mode allowed denied t
    if ! [[ "$branch" =~ ^(agent/[A-Za-z0-9._/-]+|fix/issue-[0-9]+)$ ]]; then
        echo "claude_cmd: refusing branch '$branch' (must be fix/issue-N or agent/...)" >&2
        return 1
    fi
    printf -v qprompt '%q' "$prompt"
    mode=$(cfg "$repo" claude_permission_mode)
    allowed="" denied=""
    for t in "Bash(git push origin $branch)" "Bash(git push -u origin $branch)"; do
        printf -v t '%q' "$t"; allowed+=" $t"
    done
    while IFS= read -r t; do printf -v t '%q' "$t"; allowed+=" $t"; done \
        < <(cfg "$repo" claude_allowed_tools | jq -r '.[]')
    while IFS= read -r t; do printf -v t '%q' "$t"; denied+=" $t"; done \
        < <(cfg "$repo" claude_disallowed_tools | jq -r '.[]')
    echo "cd $workdir && printf '%s' $qprompt | env -u ANTHROPIC_API_KEY -u CLAUDE_API_KEY" \
        "-u ANTHROPIC_AUTH_TOKEN -u ANTHROPIC_BASE_URL -u CLAUDE_CODE_USE_BEDROCK" \
        "-u CLAUDE_CODE_USE_VERTEX timeout 45m claude -p --max-turns 60" \
        "--permission-mode $mode --allowedTools$allowed --disallowedTools$denied"
}

# Fail closed: an unreachable box or a git error counts as dirty.
workdir_clean() {
    local out
    out=$(run_on_agent "cd $1 && git status --porcelain") || return 1
    [[ -z "$out" ]]
}

# All open PRs, agent or hand-opened. JSON array. The limit is well above any
# realistic open-PR count: a PR outside it would not block a duplicate pick.
open_prs() {
    run_on_agent "gh pr list --repo $1 --state open --limit 1000 --json number,headRefName,closingIssuesReferences,labels"
}

# Registry of PRs the worker opened: one file per PR, written after the worker confirms it.
# A fix/issue-N branch alone proves nothing (the owner may open one by hand).
pr_slug() { echo "${1//\//_}"; }

register_pr() {  # repo pr
    [[ "$AGENT_DRY_RUN" == "1" ]] && { echo "DRY-RUN: register PR $1#$2"; return 0; }
    local d tmp
    d="$AGENT_STATE_DIR/prs"
    mkdir -p "$d" || return 1
    tmp=$(mktemp "$d/.tmp.XXXXXX") || return 1
    if ! { date +%s > "$tmp" && mv "$tmp" "$d/$(pr_slug "$1")-$2"; }; then
        rm -f "$tmp"
        return 1
    fi
}

# Registration is a prerequisite: an unregistered fix/issue-N PR is ignored by the gate, so
# on failure the claim label stays and the owner is told.
finish_pr() {  # repo issue pr
    if ! register_pr "$1" "$3"; then
        notify --title "agent: PR #$3 not registered" \
            --body "$1 PR #$3 opened for #$2 but not registered, gate will not manage it. Issue keeps agent-failed." \
            --urgency warn || true
        return 1
    fi
    try_act "gh issue edit $2 --repo $1 --remove-label agent-failed"
    notify --title "agent: PR #$3 opened for #$2" --body "https://github.com/$1/pull/$3" --urgency info || true
}

# Filters open_prs JSON on stdin (arg: repo) to agent PRs: a legacy agent/ branch or `agent`
# label, or a fix/issue-N branch whose PR number is in the registry.
only_agent_prs() {
    local slug nums
    slug=$(pr_slug "$1")
    nums=$(find "$AGENT_STATE_DIR/prs" -maxdepth 1 -name "$slug-*" 2>/dev/null \
        | sed -n "s|.*/$slug-\([0-9][0-9]*\)\$|\1|p" | jq -sc '.' 2>/dev/null) || nums="[]"
    jq --argjson reg "${nums:-[]}" '[.[] | select((.headRefName | startswith("agent/"))
        or any(.labels[]; .name == "agent")
        or ((.headRefName | test("^fix/issue-[0-9]+$")) and (.number as $n | $reg | index($n))))]'
}

# Discord instead of a PR comment: one message per PR head sha and decision. The marker is
# written only after a successful send (a failed send retries next run); a failed marker
# write still notifies. State is one file per key, written atomically (temp + mv).
notify_once() {  # repo pr sha decision title body urgency
    local repo="$1" n="$2" sha="$3" decision="$4" f tmp
    f="$AGENT_STATE_DIR/notified/$(pr_slug "$repo")-$n-$sha-$decision"
    [[ -e "$f" ]] && return 0
    notify --title "$5" --body "$6" --urgency "${7:-info}" || return 0
    [[ "$AGENT_DRY_RUN" == "1" ]] && return 0
    mkdir -p "$AGENT_STATE_DIR/notified" || return 0
    tmp=$(mktemp "$AGENT_STATE_DIR/notified/.tmp.XXXXXX") || return 0
    if ! { date +%s > "$tmp" && mv "$tmp" "$f"; }; then
        rm -f "$tmp"
    fi
    return 0
}

open_agent_prs() {
    open_prs "$1" | only_agent_prs "$1"
}

ensure_labels() {
    local repo="$1" have
    have=$(run_on_agent "gh label list --repo $repo --limit 200 --json name -q '.[].name'") || return 0
    for l in agent-failed needs-human needs-split; do
        grep -qx "$l" <<<"$have" || try_act "gh label create $l --repo $repo --color BFD4F2"
    done
}

# Autofix attempts per PR, kept in a state file (not as PR labels). The first read seeds
# the count from legacy agent-fix-N labels (arg 3, read only) so in-flight PRs keep theirs.
fix_file() { echo "$AGENT_STATE_DIR/autofix/${1//\//_}-$2"; }

fix_tries() {  # repo pr legacy_count
    local f n
    f=$(fix_file "$1" "$2")
    if n=$(cat "$f" 2>/dev/null) && [[ "$n" =~ ^[0-9]+$ ]]; then
        echo "$n"
    else
        echo "${3:-0}"
    fi
}

# Returns 1 when the counter cannot be written (the caller must then not run).
fix_record() {  # repo pr new_count
    [[ "$AGENT_DRY_RUN" == "1" ]] && { echo "DRY-RUN: autofix count for $1#$2 -> $3"; return 0; }
    local f tmp
    f=$(fix_file "$1" "$2")
    mkdir -p "$(dirname "$f")" || return 1
    tmp=$(mktemp "$(dirname "$f")/.tmp.XXXXXX") || return 1
    if ! { echo "$3" > "$tmp" && mv "$tmp" "$f"; }; then
        rm -f "$tmp"
        return 1
    fi
}
