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
# refspec, --force or --delete variants). Branches: the loop's fix/issue-N (legacy agent/...)
# and the plain <type>/<slug> branches a Discord session opens its PRs from; any other
# branch gets no run at all.
# The scratch dir (from scratch_new) is added with --add-dir so the Write tool may use it.
BRANCH_RE='^(agent/[A-Za-z0-9._/-]+|fix/issue-[0-9]+|(fix|feat|refactor|test|docs|chore|perf|ci|build|style|revert)/[A-Za-z0-9._-]+)$'

claude_cmd() {
    local repo="$1" workdir="$2" prompt="$3" branch="$4" scratch="$5" allowed t
    if ! [[ "$branch" =~ $BRANCH_RE ]]; then
        echo "claude_cmd: refusing branch '$branch' (must be fix/issue-N, agent/... or <type>/<slug>)" >&2
        return 1
    fi
    if ! scratch_ok "$scratch"; then
        echo "claude_cmd: refusing scratch dir '$scratch' (must come from scratch_new)" >&2
        return 1
    fi
    allowed=""
    for t in "Bash(git push origin $branch)" "Bash(git push -u origin $branch)"; do
        printf -v t '%q' "$t"; allowed+=" $t"
    done
    while IFS= read -r t; do printf -v t '%q' "$t"; allowed+=" $t"; done \
        < <(cfg "$repo" claude_allowed_tools | jq -r '.[]')
    _claude_line "$repo" "$workdir" "$prompt" "$scratch" "$allowed" 60
}

# Read-only planning run (backlog round): it reads only the repo and writes only inside the
# scratch dir. No Bash at all (git grep -O and git log --output run or write anything), no
# GitHub or Discord credential in its environment: the prompt holds issue titles, and the
# worker creates the issues itself.
claude_plan_cmd() {
    local repo="$1" workdir="$2" prompt="$3" scratch="$4" allowed t
    if ! scratch_ok "$scratch"; then
        echo "claude_plan_cmd: refusing scratch dir '$scratch' (must come from scratch_new)" >&2
        return 1
    fi
    [[ "$workdir" =~ ^/workspace/[A-Za-z0-9_-][A-Za-z0-9._-]*$ ]] || {
        echo "claude_plan_cmd: refusing workdir '$workdir'" >&2
        return 1
    }
    # Absolute path rules (//...): Edit rules also cover the Write tool.
    allowed=""
    for t in "Read(/$workdir/**)" "Edit(/$scratch/**)"; do printf -v t '%q' "$t"; allowed+=" $t"; done
    while IFS= read -r t; do printf -v t '%q' "$t"; allowed+=" $t"; done \
        < <(cfg "$repo" claude_backlog_tools | jq -r '.[]')
    _claude_line "$repo" "$workdir" "$prompt" "$scratch" "$allowed" 30 \
        "-u GITHUB_TOKEN -u AGENT_GITHUB_TOKEN -u GH_TOKEN -u AGENT_DISCORD_WEBHOOK -u DISCORD_WEBHOOK"
}

# repo workdir prompt scratch allowed(quoted, space-led) max_turns [extra env -u flags]
_claude_line() {
    local qprompt mode denied="" t
    printf -v qprompt '%q' "$3"
    mode=$(cfg "$1" claude_permission_mode)
    while IFS= read -r t; do printf -v t '%q' "$t"; denied+=" $t"; done \
        < <(cfg "$1" claude_disallowed_tools | jq -r '.[]')
    echo "cd $2 && printf '%s' $qprompt | env -u ANTHROPIC_API_KEY -u CLAUDE_API_KEY" \
        "-u ANTHROPIC_AUTH_TOKEN -u ANTHROPIC_BASE_URL -u CLAUDE_CODE_USE_BEDROCK" \
        "-u CLAUDE_CODE_USE_VERTEX ${7:+$7 }timeout 45m claude -p --max-turns $6 --add-dir $4" \
        "--permission-mode $mode --allowedTools$5 --disallowedTools$denied"
}

# Per-run scratch dir on agent-box for commit messages, PR bodies and thread replies.
# It must be outside the repo: dontAsk refuses Write into .git/, so the model put those
# files in the work tree instead, where they stayed untracked and made workdir_clean fail
# closed for every later run (cojam, 2026-10-10). Prints the path; remove it with scratch_rm.
SCRATCH_RE='^/tmp/agent-run\.[A-Za-z0-9]{8}$'
scratch_ok() { [[ "$1" =~ $SCRATCH_RE ]]; }

scratch_new() {
    local d
    if [[ "$AGENT_DRY_RUN" == "1" ]]; then
        echo "/tmp/agent-run.DRYRUN00"
        return 0
    fi
    d=$(run_on_agent "mktemp -d /tmp/agent-run.XXXXXXXX") || return 1
    scratch_ok "$d" || return 1
    echo "$d"
}

# Best effort; a path that did not come from scratch_new (or an empty one) is ignored.
scratch_rm() {
    scratch_ok "${1:-}" || return 0
    try_act "rm -rf -- $1"
}

# Silent and 0 when the workdir is clean and detached (where the loop leaves it). Otherwise
# prints why, for the alert, and returns 1. A branch checked out means a Discord chat is (or
# was last) working there: switching under it would mix two runs in one tree.
# Fail closed: an unreachable box, a git error or no branch line counts as not clean.
workdir_clean() {
    local out head
    if ! out=$(run_on_agent "cd $1 && git status --porcelain --branch"); then
        echo "could not check: agent-box or git unreachable"
        return 1
    fi
    head=${out%%$'\n'*}
    if [[ "$head" != "## "* ]]; then
        echo "could not check: no branch line from git status"
        return 1
    fi
    # Porcelain output is not translated, so this label is stable.
    if [[ "$head" != "## HEAD (no branch)" ]]; then
        head=${head#\#\# }
        echo "branch ${head%%...*} is checked out (a chat may be using it)"
        return 1
    fi
    [[ "$out" == *$'\n'* ]] || return 0
    out=${out#*$'\n'}
    [[ -z "$out" ]] && return 0
    echo "in the way: $(dirty_summary <<<"$out")"
    return 1
}

# `git status --porcelain` on stdin -> "a, b, c and 2 more" (first 5 paths; a rename
# shows its new path).
dirty_summary() {
    awk 'NF { n++; f = substr($0, 4); if (substr($0, 1, 2) ~ /[RC]/) sub(/.* -> /, "", f)
            if (n <= 5) p = p (n > 1 ? ", " : "") f }
        END { if (n > 5) p = p " and " (n - 5) " more"; print p }'
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

# PRs a Discord session opened: owner-authored, same repo, not a loop PR, and the head commit
# is the tip of the local branch of the same name in the agent-box clone (the session pushed it
# from there). A branch the clone only has an old copy of, or that someone pushed to from
# elsewhere since, does not count. Nothing else follows these PRs once the chat ends. Prints PR
# numbers whose branch claude_cmd would accept; fails when either listing fails.
session_prs() {  # repo workdir
    local heads all loop n b
    heads=$(run_on_agent "git -C $2 for-each-ref --format='%(refname:short) %(objectname)' refs/heads/" \
        | jq -Rsc 'split("\n") | map(select(length > 0) | split(" ") | {(.[0]): .[1]}) | add // {}') || return 1
    all=$(run_on_agent "gh pr list --repo $1 --state open --limit 1000 --author $(printf '%q' "$(cfg "$1" owner)") --json number,headRefName,headRefOid,isCrossRepository,labels") || return 1
    loop=$(only_agent_prs "$1" <<<"$all" | jq -c '[.[].number]') || return 1
    while read -r n b; do
        [[ "$b" =~ $BRANCH_RE && ! "$b" =~ ^(fix/issue-[0-9]+|agent/.*)$ ]] && echo "$n"
    done < <(jq -r --argjson heads "$heads" --argjson loop "$loop" '.[]
        | select(.isCrossRepository == false and (.number as $n | $loop | index($n) | not))
        | select($heads[.headRefName] == .headRefOid)
        | "\(.number) \(.headRefName)"' <<<"$all")
    return 0
}

ensure_labels() {
    local repo="$1" have
    have=$(run_on_agent "gh label list --repo $repo --limit 200 --json name -q '.[].name'") || return 0
    for l in agent-failed needs-human needs-split ready-for-agent ready-for-human effort:s; do
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
